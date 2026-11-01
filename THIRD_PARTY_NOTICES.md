# Third-party notices

LegoEnv's first-party code is licensed under [Apache-2.0](LICENSE). The
materials listed below keep their own upstream terms; the LegoEnv license does
not supersede them. All license texts referenced here are in
[`third_party_licenses/`](third_party_licenses/).

## Code adapted from upstream projects

| Component | Upstream | License | File |
|---|---|---|---|
| BM25 ranking in `legoenv/sampling/apistyle.py` | AutomationBench, `automationbench/utils/bm25.py` at commit `4a8e1061254004d9dac807054eed33fad7d1ff14`, Copyright (c) 2026 Zapier, Inc. | MIT | `third_party_licenses/upstream-bm25-MIT.txt` |

The workflow system prompt used by the trajectory collector and the generic
API tool schema (`api_search`, `api_fetch`, `base64_encode`) originate from the
same upstream project and are retained verbatim for execution parity. No
AutomationBench task, assertion or loader is included.

## App adapters

Each app under `legoenv/apps/` (base spec plus adapter) models a subset of an
open-source application's data model and API as declared in its capability
card. No upstream application code is redistributed and no upstream service is
deployed. The table indexes the upstream repository and the retrieved license
text for every app. License names were identified from the retrieved text;
the file is authoritative. Retrieval URLs and SHA-256 hashes are in
[`third_party_licenses/app_sources.json`](third_party_licenses/app_sources.json);
qualifications for apps without a standalone license file are in
[`third_party_licenses/SOURCE_LICENSE_NOTES.md`](third_party_licenses/SOURCE_LICENSE_NOTES.md).
Upstream files were retrieved from the default branch (`HEAD`); the commit used
when each spec was originally extracted was not recorded.

| App | Upstream repository | License (detected from text) | File |
|---|---|---|---|
| 4gaboards | https://github.com/rargames/4gaboards | MIT | `third_party_licenses/apps/4gaboards.txt` |
| accent | https://github.com/mirego/accent | BSD-3-Clause | `third_party_licenses/apps/accent.txt` |
| actual | https://github.com/actualbudget/actual | MIT | `third_party_licenses/apps/actual.txt` |
| airtrail | https://github.com/johanohly/airtrail | GPL-3.0 | `third_party_licenses/apps/airtrail.txt` |
| alf_io | https://github.com/alfio-event/alf.io | GPL-3.0 | `third_party_licenses/apps/alf_io.txt` |
| ampache | https://github.com/ampache/ampache | AGPL-3.0 | `third_party_licenses/apps/ampache.txt` |
| anonaddy | https://github.com/anonaddy/anonaddy | AGPL-3.0 | `third_party_licenses/apps/anonaddy.txt` |
| answer | https://github.com/apache/answer | Apache-2.0 | `third_party_licenses/apps/answer.txt` |
| anything_llm | https://github.com/mintplex-labs/anything-llm | MIT | `third_party_licenses/apps/anything_llm.txt` |
| app | https://github.com/simple-login/app | AGPL-3.0 | `third_party_licenses/apps/app.txt` |
| artalk | https://github.com/artalkjs/artalk | MIT | `third_party_licenses/apps/artalk.txt` |
| audiobookshelf | https://github.com/advplyr/audiobookshelf | GPL-3.0 | `third_party_licenses/apps/audiobookshelf.txt` |
| bagisto | https://github.com/bagisto/bagisto | MIT | `third_party_licenses/apps/bagisto.txt` |
| bitwarden_server | https://github.com/bitwarden/server | AGPL-3.0 / Bitwarden License v1.0 | `third_party_licenses/apps/bitwarden_server.txt` |
| bookwyrm | https://github.com/bookwyrm-social/bookwyrm | MIT | `third_party_licenses/apps/bookwyrm.txt` |
| bracket | https://github.com/evroon/bracket | AGPL-3.0 | `third_party_licenses/apps/bracket.txt` |
| btcpayserver | https://github.com/btcpayserver/btcpayserver | MIT | `third_party_licenses/apps/btcpayserver.txt` |
| bugsink | https://github.com/bugsink/bugsink | Mixed (see file) | `third_party_licenses/apps/bugsink.txt` |
| bugzilla | https://github.com/bugzilla/bugzilla | GPL-3.0 | `third_party_licenses/apps/bugzilla.txt` |
| cal_diy | https://github.com/calcom/cal.diy | MIT | `third_party_licenses/apps/cal_diy.txt` |
| calibre | https://github.com/kovidgoyal/calibre | GPL-3.0 | `third_party_licenses/apps/calibre.txt` |
| calibre_web | https://github.com/janeczku/calibre-web | GPL-3.0 | `third_party_licenses/apps/calibre_web.txt` |
| chat | https://github.com/tinode/chat | GPL-3.0 | `third_party_licenses/apps/chat.txt` |
| chibisafe | https://github.com/chibisafe/chibisafe | MIT | `third_party_licenses/apps/chibisafe.txt` |
| chyrp_lite | https://github.com/xenocrat/chyrp-lite | BSD-3-Clause | `third_party_licenses/apps/chyrp_lite.txt` |
| claper | https://github.com/claperco/claper | AGPL-3.0 | `third_party_licenses/apps/claper.txt` |
| clipbucket_v5 | https://github.com/macwarrior/clipbucket-v5 | BSD-3-Clause | `third_party_licenses/apps/clipbucket_v5.txt` |
| coder | https://github.com/coder/coder | AGPL-3.0 | `third_party_licenses/apps/coder.txt` |
| copyparty | https://github.com/9001/copyparty | MIT | `third_party_licenses/apps/copyparty.txt` |
| corteza | https://github.com/cortezaproject/corteza | Apache-2.0 | `third_party_licenses/apps/corteza.txt` |
| cryptpad | https://github.com/cryptpad/cryptpad | AGPL-3.0 | `third_party_licenses/apps/cryptpad.txt` |
| diaspora | https://github.com/diaspora/diaspora | AGPL-3.0 | `third_party_licenses/apps/diaspora.txt` |
| django_crm | https://github.com/djangocrm/django-crm | AGPL-3.0 | `third_party_licenses/apps/django_crm.txt` |
| docassemble | https://github.com/jhpyle/docassemble | MIT | `third_party_licenses/apps/docassemble.txt` |
| docspell | https://github.com/eikek/docspell | AGPL-3.0 | `third_party_licenses/apps/docspell.txt` |
| dokuwiki | https://github.com/dokuwiki/dokuwiki | GPL-2.0 | `third_party_licenses/apps/dokuwiki.txt` |
| donetick | https://github.com/donetick/donetick | AGPL-3.0 | `third_party_licenses/apps/donetick.txt` |
| dspace | https://github.com/dspace/dspace | BSD-3-Clause | `third_party_licenses/apps/dspace.txt` |
| egroupware | https://github.com/egroupware/egroupware | GPL-2.0 | `third_party_licenses/apps/egroupware.txt` |
| ente | https://github.com/ente-io/ente | AGPL-3.0 | `third_party_licenses/apps/ente.txt` |
| ergo | https://github.com/ergochat/ergo | MIT | `third_party_licenses/apps/ergo.txt` |
| erpnext | https://github.com/frappe/erpnext | Not retrieved | none |
| erxes | https://github.com/erxes/erxes | Mixed (see file) | `third_party_licenses/apps/erxes.txt` |
| etherpad | https://github.com/ether/etherpad | Apache-2.0 | `third_party_licenses/apps/etherpad.txt` |
| ever_traduora | https://github.com/ever-co/ever-traduora | AGPL-3.0 | `third_party_licenses/apps/ever_traduora.txt` |
| filebrowser | https://github.com/filebrowser/filebrowser | Apache-2.0 | `third_party_licenses/apps/filebrowser.txt` |
| filegator | https://github.com/filegator/filegator | MIT | `third_party_licenses/apps/filegator.txt` |
| firefly_iii | https://github.com/firefly-iii/firefly-iii | AGPL-3.0 | `third_party_licenses/apps/firefly_iii.txt` |
| fittrackee | https://github.com/samr1/fittrackee | AGPL-3.0 | `third_party_licenses/apps/fittrackee.txt` |
| foodsoft | https://github.com/foodcoops/foodsoft | AGPL-3.0 | `third_party_licenses/apps/foodsoft.txt` |
| formbricks | https://github.com/formbricks/formbricks | Mixed (see file) | `third_party_licenses/apps/formbricks.txt` |
| freescout | https://github.com/freescout-help-desk/freescout | AGPL-3.0 | `third_party_licenses/apps/freescout.txt` |
| fusionpbx | https://github.com/fusionpbx/fusionpbx | MPL-1.1 (file header only) | none |
| ghost | https://github.com/tryghost/ghost | MIT | `third_party_licenses/apps/ghost.txt` |
| gitbucket | https://github.com/gitbucket/gitbucket | Apache-2.0 | `third_party_licenses/apps/gitbucket.txt` |
| gitea | https://github.com/go-gitea/gitea | MIT | `third_party_licenses/apps/gitea.txt` |
| gogs | https://github.com/gogs/gogs | MIT | `third_party_licenses/apps/gogs.txt` |
| gokapi | https://github.com/forceu/gokapi | AGPL-3.0 | `third_party_licenses/apps/gokapi.txt` |
| gollum | https://github.com/gollum/gollum | MIT | `third_party_licenses/apps/gollum.txt` |
| grist_core | https://github.com/gristlabs/grist-core | Apache-2.0 | `third_party_licenses/apps/grist_core.txt` |
| grocy | https://github.com/grocy/grocy | MIT | `third_party_licenses/apps/grocy.txt` |
| groupoffice | https://github.com/intermesh/groupoffice | AGPL-3.0 | `third_party_licenses/apps/groupoffice.txt` |
| habitica | https://github.com/habitrpg/habitica | GPL | `third_party_licenses/apps/habitica.txt` |
| halo | https://github.com/halo-dev/halo | GPL-3.0 | `third_party_licenses/apps/halo.txt` |
| haven | https://github.com/havenweb/haven | MIT | `third_party_licenses/apps/haven.txt` |
| hedgedoc | https://github.com/hedgedoc/hedgedoc | AGPL-3.0 | `third_party_licenses/apps/hedgedoc.txt` |
| hemmelig_app | https://github.com/hemmeligorg/hemmelig.app | MIT | `third_party_licenses/apps/hemmelig_app.txt` |
| homarr | https://github.com/homarr-labs/homarr | Apache-2.0 | `third_party_licenses/apps/homarr.txt` |
| home_gallery | https://github.com/xemle/home-gallery | MIT | `third_party_licenses/apps/home_gallery.txt` |
| homebox | https://github.com/sysadminsmedia/homebox | AGPL-3.0 | `third_party_licenses/apps/homebox.txt` |
| hoppscotch | https://github.com/hoppscotch/hoppscotch | MIT | `third_party_licenses/apps/hoppscotch.txt` |
| htmly | https://github.com/danpros/htmly | GPL-2.0 | `third_party_licenses/apps/htmly.txt` |
| humhub | https://github.com/humhub/humhub | AGPL-3.0 | `third_party_licenses/apps/humhub.txt` |
| hyperswitch | https://github.com/juspay/hyperswitch | Apache-2.0 | `third_party_licenses/apps/hyperswitch.txt` |
| hyrax | https://github.com/samvera/hyrax | Apache-2.0 | `third_party_licenses/apps/hyrax.txt` |
| idno | https://github.com/idno/idno | Apache-2.0 | `third_party_licenses/apps/idno.txt` |
| invoiceninja | https://github.com/invoiceninja/invoiceninja | Elastic-2.0 | `third_party_licenses/apps/invoiceninja.txt` |
| invoiceplane | https://github.com/invoiceplane/invoiceplane | MIT | `third_party_licenses/apps/invoiceplane.txt` |
| invoiceshelf | https://github.com/invoiceshelf/invoiceshelf | AGPL-3.0 | `third_party_licenses/apps/invoiceshelf.txt` |
| isso | https://github.com/isso-comments/isso | MIT | `third_party_licenses/apps/isso.txt` |
| itflow | https://github.com/itflow-org/itflow | GPL-3.0 | `third_party_licenses/apps/itflow.txt` |
| kanboard | https://github.com/kanboard/kanboard | MIT | `third_party_licenses/apps/kanboard.txt` |
| khoj | https://github.com/khoj-ai/khoj | AGPL-3.0 | `third_party_licenses/apps/khoj.txt` |
| kimai | https://github.com/kimai/kimai | AGPL-3.0 | `third_party_licenses/apps/kimai.txt` |
| koel | https://github.com/koel/koel | MIT | `third_party_licenses/apps/koel.txt` |
| koha | https://github.com/koha-community/koha | GPL-3.0 | `third_party_licenses/apps/koha.txt` |
| laravel_crm | https://github.com/krayin/laravel-crm | MIT | `third_party_licenses/apps/laravel_crm.txt` |
| lemmy | https://github.com/lemmynet/lemmy | AGPL-3.0 | `third_party_licenses/apps/lemmy.txt` |
| linkace | https://github.com/kovah/linkace | GPL-3.0 | `third_party_licenses/apps/linkace.txt` |
| linkwarden | https://github.com/linkwarden/linkwarden | AGPL-3.0 | `third_party_licenses/apps/linkwarden.txt` |
| local_deep_research | https://github.com/learningcircuit/local-deep-research | MIT | `third_party_licenses/apps/local_deep_research.txt` |
| lychee | https://github.com/lycheeorg/lychee | MIT | `third_party_licenses/apps/lychee.txt` |
| mataroa | https://github.com/mataroablog/mataroa | AGPL-3.0 | `third_party_licenses/apps/mataroa.txt` |
| mautic | https://github.com/mautic/mautic | GPL-3.0 | `third_party_licenses/apps/mautic.txt` |
| mealie | https://github.com/mealie-recipes/mealie | AGPL-3.0 | `third_party_licenses/apps/mealie.txt` |
| mediacms | https://github.com/mediacms-io/mediacms | AGPL-3.0 | `third_party_licenses/apps/mediacms.txt` |
| memos | https://github.com/usememos/memos | MIT | `third_party_licenses/apps/memos.txt` |
| meshcentral | https://github.com/ylianst/meshcentral | Apache-2.0 | `third_party_licenses/apps/meshcentral.txt` |
| minds | https://github.com/mindsdb/minds | MIT | `third_party_licenses/apps/minds.txt` |
| miniserve | https://github.com/svenstaro/miniserve | MIT | `third_party_licenses/apps/miniserve.txt` |
| monica | https://github.com/monicahq/monica | AGPL-3.0 | `third_party_licenses/apps/monica.txt` |
| n8n | https://github.com/n8n-io/n8n | Mixed (see file) | `third_party_licenses/apps/n8n.txt` |
| navidrome | https://github.com/navidrome/navidrome | GPL-3.0 | `third_party_licenses/apps/navidrome.txt` |
| nocodb | https://github.com/nocodb/nocodb | Mixed (see file) | `third_party_licenses/apps/nocodb.txt` |
| node_red | https://github.com/node-red/node-red | Apache-2.0 | `third_party_licenses/apps/node_red.txt` |
| nodebb | https://github.com/nodebb/nodebb | GPL-3.0 | `third_party_licenses/apps/nodebb.txt` |
| october | https://github.com/octobercms/october | Proprietary EULA | `third_party_licenses/apps/october.txt` |
| octoprint | https://github.com/octoprint/octoprint | AGPL-3.0 | `third_party_licenses/apps/octoprint.txt` |
| ofbiz_framework | https://github.com/apache/ofbiz-framework | Apache-2.0 | `third_party_licenses/apps/ofbiz_framework.txt` |
| ollama | https://github.com/ollama/ollama | MIT | `third_party_licenses/apps/ollama.txt` |
| ombi | https://github.com/ombi-app/ombi | GPL-2.0 | `third_party_licenses/apps/ombi.txt` |
| opencart | https://github.com/opencart/opencart | GPL-3.0 | `third_party_licenses/apps/opencart.txt` |
| openfire | https://github.com/igniterealtime/openfire | Apache-2.0 | `third_party_licenses/apps/openfire.txt` |
| openfoodnetwork | https://github.com/openfoodfoundation/openfoodnetwork | AGPL-3.0 | `third_party_licenses/apps/openfoodnetwork.txt` |
| opensourcepos | https://github.com/opensourcepos/opensourcepos | MIT | `third_party_licenses/apps/opensourcepos.txt` |
| openstreetmap_website | https://github.com/openstreetmap/openstreetmap-website | GPL-2.0 | `third_party_licenses/apps/openstreetmap_website.txt` |
| opnform | https://github.com/opnform/opnform | Mixed (see file) | `third_party_licenses/apps/opnform.txt` |
| osem | https://github.com/opensuse/osem | MIT | `third_party_licenses/apps/osem.txt` |
| overleaf | https://github.com/overleaf/overleaf | AGPL-3.0 | `third_party_licenses/apps/overleaf.txt` |
| owncast | https://github.com/owncast/owncast | MIT | `third_party_licenses/apps/owncast.txt` |
| owncloud_core | https://github.com/owncloud/core | AGPL-3.0 | `third_party_licenses/apps/owncloud_core.txt` |
| part_db_server | https://github.com/part-db/part-db-server | AGPL-3.0 | `third_party_licenses/apps/part_db_server.txt` |
| passbolt_api | https://github.com/passbolt/passbolt_api | AGPL-3.0 | `third_party_licenses/apps/passbolt_api.txt` |
| peertube | https://github.com/chocobozzz/peertube | AGPL-3.0 | `third_party_licenses/apps/peertube.txt` |
| pelican_dev_panel | https://github.com/pelican-dev/panel | AGPL-3.0 | `third_party_licenses/apps/pelican_dev_panel.txt` |
| photoprism | https://github.com/photoprism/photoprism | AGPL-3.0 | `third_party_licenses/apps/photoprism.txt` |
| phpbb | https://github.com/phpbb/phpbb | GPL-2.0 | `third_party_licenses/apps/phpbb.txt` |
| phplist3 | https://github.com/phplist/phplist3 | AGPL-3.0 | `third_party_licenses/apps/phplist3.txt` |
| piga | https://github.com/nymanjens/piga | Apache-2.0 | `third_party_licenses/apps/piga.txt` |
| pigallery2 | https://github.com/bpatrik/pigallery2 | MIT | `third_party_licenses/apps/pigallery2.txt` |
| piwigo | https://github.com/piwigo/piwigo | GPL-2.0 | `third_party_licenses/apps/piwigo.txt` |
| pixelfed | https://github.com/pixelfed/pixelfed | AGPL-3.0 | `third_party_licenses/apps/pixelfed.txt` |
| podfetch | https://github.com/samtv12345/podfetch | Apache-2.0 | `third_party_licenses/apps/podfetch.txt` |
| postal | https://github.com/postalserver/postal | Not retrieved | none |
| prestashop | https://github.com/prestashop/prestashop | OSL-3.0 (core) / AFL-3.0 (modules) | `third_party_licenses/apps/prestashop.txt` |
| pretalx | https://github.com/pretalx/pretalx | AGPL-3.0 | `third_party_licenses/apps/pretalx.txt` |
| puter | https://github.com/heyputer/puter | AGPL-3.0 | `third_party_licenses/apps/puter.txt` |
| qloapps | https://github.com/qloapps/qloapps | OSL-3.0 | `third_party_licenses/apps/qloapps.txt` |
| radicale | https://github.com/kozea/radicale | GPL-3.0 | `third_party_licenses/apps/radicale.txt` |
| raneto | https://github.com/ryanlelek/raneto | MIT | `third_party_licenses/apps/raneto.txt` |
| reactive_resume | https://github.com/amruthpillai/reactive-resume | MIT | `third_party_licenses/apps/reactive_resume.txt` |
| recipes | https://github.com/tandoorrecipes/recipes | AGPL-3.0 | `third_party_licenses/apps/recipes.txt` |
| recipesage | https://github.com/julianpoy/recipesage | AGPL-3.0 non-commercial / commercial by request | none |
| relate | https://github.com/inducer/relate | MIT | `third_party_licenses/apps/relate.txt` |
| remark42 | https://github.com/umputun/remark42 | MIT | `third_party_licenses/apps/remark42.txt` |
| rocket_chat | https://github.com/rocketchat/rocket.chat | Mixed (see file) | `third_party_licenses/apps/rocket_chat.txt` |
| saleor | https://github.com/saleor/saleor | BSD-3-Clause | `third_party_licenses/apps/saleor.txt` |
| seaweedfs | https://github.com/seaweedfs/seaweedfs | Apache-2.0 | `third_party_licenses/apps/seaweedfs.txt` |
| seerr | https://github.com/seerr-team/seerr | MIT | `third_party_licenses/apps/seerr.txt` |
| sentry | https://github.com/getsentry/sentry | FSL-1.1 (Apache-2.0 future) | `third_party_licenses/apps/sentry.txt` |
| sftpgo | https://github.com/drakkan/sftpgo | AGPL-3.0 | `third_party_licenses/apps/sftpgo.txt` |
| shelf_nu | https://github.com/shelf-nu/shelf.nu | Mixed (see file) | `third_party_licenses/apps/shelf_nu.txt` |
| slskd | https://github.com/slskd/slskd | AGPL-3.0 | `third_party_licenses/apps/slskd.txt` |
| snappymail | https://github.com/the-djmaze/snappymail | AGPL-3.0 | `third_party_licenses/apps/snappymail.txt` |
| spoolman | https://github.com/donkie/spoolman | MIT | `third_party_licenses/apps/spoolman.txt` |
| spree | https://github.com/spree/spree | BSD-3-Clause | `third_party_licenses/apps/spree.txt` |
| stirling_pdf | https://github.com/stirling-tools/stirling-pdf | Mixed (see file) | `third_party_licenses/apps/stirling_pdf.txt` |
| svix_webhooks | https://github.com/svix/svix-webhooks | MIT | `third_party_licenses/apps/svix_webhooks.txt` |
| sylius | https://github.com/sylius/sylius | MIT | `third_party_licenses/apps/sylius.txt` |
| sync | https://github.com/calzoneman/sync | MIT | `third_party_licenses/apps/sync.txt` |
| teampass | https://github.com/nilsteampassnet/teampass | GPL-3.0 | `third_party_licenses/apps/teampass.txt` |
| thelounge | https://github.com/thelounge/thelounge | MIT | `third_party_licenses/apps/thelounge.txt` |
| thingsboard | https://github.com/thingsboard/thingsboard | Apache-2.0 | `third_party_licenses/apps/thingsboard.txt` |
| tiddlywiki5 | https://github.com/tiddlywiki/tiddlywiki5 | BSD-3-Clause | `third_party_licenses/apps/tiddlywiki5.txt` |
| tolgee_platform | https://github.com/tolgee/tolgee-platform | Mixed (see file) | `third_party_licenses/apps/tolgee_platform.txt` |
| tracim | https://github.com/tracim/tracim | Mixed (AGPL-3.0 / LGPL-3.0 / MIT, see file) | `third_party_licenses/apps/tracim.txt` |
| tracks | https://github.com/tracksapp/tracks | GPL-2.0 | `third_party_licenses/apps/tracks.txt` |
| trilium | https://github.com/triliumnext/trilium | AGPL-3.0 | `third_party_licenses/apps/trilium.txt` |
| umami | https://github.com/umami-software/umami | MIT | `third_party_licenses/apps/umami.txt` |
| vaultwarden | https://github.com/dani-garcia/vaultwarden | AGPL-3.0 | `third_party_licenses/apps/vaultwarden.txt` |
| vendure | https://github.com/vendurehq/vendure | GPL-3.0 | `third_party_licenses/apps/vendure.txt` |
| wagtail | https://github.com/wagtail/wagtail | BSD-3-Clause | `third_party_licenses/apps/wagtail.txt` |
| wallos | https://github.com/ellite/wallos | GPL-3.0 | `third_party_licenses/apps/wallos.txt` |
| wanderer | https://github.com/open-wanderer/wanderer | AGPL-3.0 | `third_party_licenses/apps/wanderer.txt` |
| wekan | https://github.com/wekan/wekan | MIT | `third_party_licenses/apps/wekan.txt` |
| wger | https://github.com/wger-project/wger | AGPL-3.0 | `third_party_licenses/apps/wger.txt` |
| wiki | https://github.com/requarks/wiki | AGPL-3.0 | `third_party_licenses/apps/wiki.txt` |
| wordpress | https://github.com/wordpress/wordpress | GPL-2.0 | `third_party_licenses/apps/wordpress.txt` |
| writefreely | https://github.com/writefreely/writefreely | AGPL-3.0 | `third_party_licenses/apps/writefreely.txt` |
| zammad | https://github.com/zammad/zammad | AGPL-3.0 | `third_party_licenses/apps/zammad.txt` |
## Datasets

Seed rows used to populate environments come from public datasets. The data
release carries the full per-source ledger (`DATA_LICENSES.tsv`, 169 rows with
URLs, declared licenses and usage counts); rows marked `restricted_hold` or
`unknown_hold` are not redistributed. License texts retrieved for the
following sources are included here (identities in
[`third_party_licenses/datasets/SOURCE_LICENSE_FILES.json`](third_party_licenses/datasets/SOURCE_LICENSE_FILES.json)):

| Dataset | License source | License (detected from text) | File |
|---|---|---|---|
| us-congress-legislators | https://github.com/unitedstates/congress-legislators | CC0-1.0 | `third_party_licenses/datasets/us-congress-legislators.txt` |
| met-museum-openaccess | https://github.com/metmuseum/openaccess | CC0-1.0 | `third_party_licenses/datasets/met-museum-openaccess.txt` |
| spoolman-db-filament-catalog | https://github.com/Donkie/SpoolmanDB | MIT | `third_party_licenses/datasets/spoolman-db-filament-catalog.txt` |
| bdg2-building-energy-telemetry | https://github.com/buds-lab/building-data-genome-project-2 | CC-BY-SA-4.0 | `third_party_licenses/datasets/bdg2-building-energy-telemetry.txt` |
## Data and model licenses

First-party skeletons, atoms, goals, verifiers, reference witnesses,
trajectories and manifests are released under CC BY 4.0 with the data release.
Qwen base-model weights and derived checkpoints keep the base model's license.
