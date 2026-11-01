"""Bagisto attachment: scalar catalog/admin operations and dual auth realms.

No tool is invented. Sparse read interfaces and upstream behavior absent from
the supplied executor are explicitly restricted in NOTES and the card.
"""
import json
import runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP = 'bagisto'
NEW_SERVER = {APP:'commerce'}
NEW_CONTENT = {APP:[
    'CoreConfig','Address','SubscribersList','Section','SectionTranslation',
    'Order','OrderItem','OrderAddress','OrderPayment','OrderComment','OrderTransaction',
    'Invoice','InvoiceItem','Shipment','ShipmentItem','Refund','RefundItem',
    'DownloadableLinkPurchased','Product','ProductAttributeValue','ProductFlat',
    'ProductInventory','ProductSalableInventory','ProductInventoryIndex','ProductPriceIndex',
    'ProductOrderedInventory','ProductReview','ProductReviewAttachment','ProductImage',
    'ProductImageTranslation','ProductVideo','ProductDownloadableLink',
    'ProductDownloadableLinkTranslation','ProductDownloadableSample',
    'ProductDownloadableSampleTranslation','ProductBundleOption','ProductBundleOptionTranslation',
    'ProductBundleOptionProduct','ProductGroupedProduct','ProductCustomerGroupPrice',
    'ProductCustomizableOption','ProductCustomizableOptionTranslation','ProductCustomizableOptionPrice',
    'ProductChannel','ProductCategory','ProductRelation','ProductSuperAttribute','ProductUpSell',
    'ProductCrossSell','CustomerAddress','CustomerNote','Wishlist','CompareItem',
    'Cart','CartItem','CartAddress','CartPayment','CartShippingRate',
]}
NEW_NOTES = {APP:(
    '{p}__ is the Bagisto commerce app. For admin work sign in with '
    '{p}__admin_login(email, password); admin persona id is 1. Customer tools use '
    'a separate realm: call {p}__customer_login(email, password) using the same supplied '
    'credentials before customer tools, and admin_login again before returning to admin work. '
    'Customer persona id is also 1. product_search(query) lists products by optional '
    'SKU/type substring; omit query to list all products. It returns Product scalar rows '
    '(id, sku, type, attribute_family_id), not flattened names/prices. '
    'productreview_list(product_id, q) reads reviews, optionally filtering title/comment; '
    'productreview_updatestatus(id,status) moderates a review (pending/approved/disapproved). '
    'refund_getorderitemsrefundsummary(order_id) returns the existing Order row, including '
    'status and shipping_description where handling policies may be stored; it does not calculate '
    'a refund. Order ids must be supplied by the task because there is no order-list tool. '
    'order_comment(order_id,comment,customer_notified) records an order note; '
    'order_cancel(id) changes scalar order status to cancelled. '
    'product_create(type,attribute_family_id,sku) creates a product using attribute family 1; '
    'product_delete(id) and productreview_delete(id) delete those records. '
    'productinventory_save(id=<product id>,qty) changes an existing, preseeded inventory row. '
    'This tool panel has no inventory/cart-item/address/comment list interfaces. '
    'The product_update upsert key merges different attributes of one product and cannot safely '
    'edit a general multi-attribute catalog. Order/invoice/refund/shipment creation does not '
    'realize their full nested lines or financial calculations; checkout_storeorder only '
    'changes Cart state and does not create an Order. Do not infer those effects from names.'
)}
LOGIN = {APP:('admin_login','email')}
SERVER.update(NEW_SERVER)
PFX[APP] = 'bagisto'
CONTENT.update(NEW_CONTENT)
NOTES.update(NEW_NOTES)
packlib.LOGIN.update(LOGIN)

OBS_READS = ['product_search','productreview_list','refund_getorderitemsrefundsummary']
_original_obs = World.obs_report

def _obs_report(self):
    rep,bad = _original_obs(self)
    if APP not in self.apps:
        return rep,bad
    env = runtime.Env(self.world)
    login = env.call(NS(APP,'admin_login'),{'email':self.persona,'password':self.password})
    if not login.get('ok'):
        raise RuntimeError(f'Bagisto observation login failed: {login}')
    reads = [('product_search',{})]
    reads += [('productreview_list',{'product_id':r['id']}) for r in env.state.get(NS(APP,'Product'),[])]
    reads += [('refund_getorderitemsrefundsummary',{'order_id':r['id']}) for r in env.state.get(NS(APP,'Order'),[])]
    for tool,args in reads:
        result = env.call(NS(APP,tool),args)
        if not result.get('ok'):
            raise RuntimeError(f'Bagisto observation {tool} failed: {result}')
        key = f'{APP} {tool}' + (f' {next(iter(args.values()))}' if args else '')
        rep[key] = len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{key:size for key,size in rep.items() if size>OBS_CAP}

World.obs_report = _obs_report

def _append(W,entity,rows,src=None):
    rows = [dict(row) for row in rows]
    for row in rows:
        if not isinstance(row.get('id'),int) or isinstance(row['id'],bool):
            raise ValueError(f'{entity} seed ids must be integers')
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:
        W.bindings[NS(APP,entity)] = {'dataset':src,'rows':len(rows)}
    return rows

def products(W,rows,src=None):
    """[{id,sku,type?,attribute_family_id?}]; no implicit EAV/flat projections."""
    return _append(W,'Product',[{'type':'simple','attribute_family_id':1,**r} for r in rows],src)

def orders(W,rows,src=None):
    """[{id,increment_id,status?,shipping_description?}]; notes may hold policy."""
    return _append(W,'Order',[{'status':'pending','customer_id':1,'channel_id':1,**r} for r in rows],src)

def reviews(W,rows,src=None):
    return _append(W,'ProductReview',[{'name':'Store customer','rating':4,'status':'pending','customer_id':1,**r} for r in rows],src)

def inventory(W,rows,src=None):
    return _append(W,'ProductInventory',[{'inventory_source_id':1,'vendor_id':0,'qty':0,**r} for r in rows],src)

def carts(W,rows,items=(),src=None):
    _append(W,'Cart',[{'customer_id':1,'channel_id':1,'is_active':True,**r} for r in rows],src)
    return _append(W,'CartItem',[{'quantity':1,**r} for r in items],src)

def smoke_seed(W):
    products(W,[
        {'id':101,'sku':'MUG-101'},
        {'id':102,'sku':'TOWEL-102'},
        {'id':103,'sku':'GLASS-103'},
    ])
    orders(W,[
        {'id':1001,'increment_id':'STORE-1001','shipping_description':
            'Policy: cancel a duplicate order only after adding an internal review note. '
            'Do not cancel the completed order STORE-1002 or the reserved order STORE-1003.'},
        {'id':1002,'increment_id':'STORE-1002','status':'completed','shipping_description':'Delivered order; retain history.'},
        {'id':1003,'increment_id':'STORE-1003','status':'pending','shipping_description':'Reserved order; retain pending status.'},
    ])
    reviews(W,[{'id':201,'product_id':101,'title':'Useful mug','comment':'Arrived safely; useful handle.'}])
    inventory(W,[{'id':301,'product_id':101,'qty':5}])
    steps = [
        (APP,'order_comment',{'order_id':1001,'comment':'Duplicate order reviewed; cancellation approved.','customer_notified':False}),
        (APP,'order_cancel',{'id':1001}),
        (APP,'productreview_updatestatus',{'id':201,'status':'approved'}),
        (APP,'productinventory_save',{'id':101,'qty':8}),
    ]
    predicates = [
        ('noted','The duplicate order has an internal cancellation review note.',
         CNT(SEL(NS(APP,'OrderComment'),AND(F('order_id','eq',1001),F('comment','eq','Duplicate order reviewed; cancellation approved.'),F('customer_notified','eq',False)))),False),
        ('cancelled','The duplicate order status is cancelled.',
         CNT(SEL(NS(APP,'Order'),AND(F('id','eq',1001),F('status','eq','cancelled')))),False),
        ('moderated','The mug review is approved.',
         CNT(SEL(NS(APP,'ProductReview'),AND(F('id','eq',201),F('status','eq','approved')))),False),
        ('stocked','The existing mug inventory row has quantity eight.',
         CNT(SEL(NS(APP,'ProductInventory'),AND(F('product_id','eq',101),F('qty','eq',8)))),False),
        ('reserved_unchanged','The reserved order remains pending.',
         CNT(SEL(NS(APP,'Order'),AND(F('id','eq',1003),F('status','eq','pending')))),True),
    ]
    return steps,predicates

__all__ = ['NEW_SERVER','products','orders','reviews','inventory','carts','smoke_seed']
