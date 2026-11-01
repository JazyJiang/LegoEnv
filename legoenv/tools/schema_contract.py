#!/usr/bin/env python3
"""Row-free schema and exact generated-shape validation, standard library only."""
import math
import re


def exact_keys(obj, required, optional=()):
    if not isinstance(obj, dict) or not set(required) <= set(obj) or not set(obj) <= set(required) | set(optional):
        raise ValueError('Unexpected keys in an allowlisted generation input')


def schema_card(card):
    exact_keys(card, ['dataset_id', 'tables', 'status'])
    for table in card['tables']:
        exact_keys(table, ['table', 'columns', 'row_count', 'row_count_exact'])
        for col in table['columns']:
            exact_keys(col, ['name', 'type'])
            if not isinstance(col['name'], str) or not isinstance(col['type'], str):
                raise ValueError('Column name and type must be text')
        if len({col['name'] for col in table['columns']}) != len(table['columns']):
            raise ValueError('Duplicate column identifiers')
        if not isinstance(table['row_count_exact'], bool):
            raise ValueError('Exact-count flag must be boolean')
        n = table['row_count']
        if n is not None and (not isinstance(n, int) or isinstance(n, bool) or n < 0):
            raise ValueError('Invalid row count')
    if card['status'] == 'ready' and (not card['tables'] or not all(
            x['columns'] and x['row_count_exact'] is True and isinstance(x['row_count'], int) for x in card['tables'])):
        raise ValueError('Unconfirmed shape marked ready')


def generated_data(card, result):
    """Validate generated shape only; business consistency is a separate builder check."""
    schema_card(card)
    if card['status'] != 'ready':
        raise ValueError('Cannot generate against an unconfirmed schema')
    exact_keys(result, ['dataset_id', 'tables'])
    if result['dataset_id'] != card['dataset_id'] or len(result['tables']) != len(card['tables']):
        raise ValueError('Dataset or table identity changed')
    for schema, table in zip(card['tables'], result['tables']):
        exact_keys(table, ['table', 'rows'])
        if table['table'] != schema['table'] or len(table['rows']) != schema['row_count']:
            raise ValueError('Table identity or exact row count changed')
        keys = [x['name'] for x in schema['columns']]
        for row in table['rows']:
            exact_keys(row, keys)
            for col in schema['columns']:
                value = row[col['name']]
                if value is None:
                    continue  # Original cards do not specify nullability.
                kind = col['type'].lower().strip().split('|')[0]
                integer = kind in {'integer', 'long', 'source-row-id', 'integer (0/1)'} or bool(re.fullmatch(r'u?int(?:8|16|32|64)?', kind))
                numeric = integer or kind in {'numeric', 'float', 'number', 'double', 'decimal', 'gbp_amount', 'derived-numeric'} or kind.startswith(('decimal128(', 'float32', 'float64'))
                textual = kind in {'text', 'str', 'string', 'category', 'categorical', 'date', 'datetime', 'timestamp', 'varchar', 'url', 'entity', 'contact'} or kind.startswith(('timestamp[', 'date32['))
                array = kind.startswith(('list', 'array')) or kind == 'category_list'
                structured = kind.startswith('struct') or kind == 'object'
                if numeric and (not isinstance(value, (int, float)) or isinstance(value, bool)):
                    raise ValueError('Non-numeric generated cell')
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError('Non-finite generated cell')
                if integer and not isinstance(value, int):
                    raise ValueError('Non-integral generated cell')
                if kind in {'bool', 'boolean'} and not isinstance(value, bool):
                    raise ValueError('Non-boolean generated cell')
                if textual and not isinstance(value, str):
                    raise ValueError('Non-text generated cell')
                if array and not isinstance(value, list):
                    raise ValueError('Non-array generated cell')
                if structured and not isinstance(value, dict):
                    raise ValueError('Non-object generated cell')
                if kind == 'id' and (not isinstance(value, (str, int)) or isinstance(value, bool)):
                    raise ValueError('Identifier must be a string or integer')
                if kind in {'null', 'nonetype'}:
                    raise ValueError('Non-null value in a null-typed column')
                if not (numeric or textual or array or structured or kind in {'bool', 'boolean', 'id'}):
                    raise ValueError('Unsupported declared type: '+kind)
