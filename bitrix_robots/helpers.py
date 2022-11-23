
def get_php_style_list(query_dict, param, default=None):
    """Возвращает списком параметры типа:
    ?foo[]=1&foo[]=2
    и
    ?foo[0]=1&foo[1]=2
    Example:
        GET /my_view?user_id[0]=42&user_id[1]=666
        GET /my_view?user_id[]=42&user_id[]=666
        user_ids = get_php_style_list(request.GET, 'user_id', []) // ['42', '666']
    """
    if param.endswith('[]'):
        param, _ = param.rsplit('[]', 1)
    param_with_brackets = '{param}[]'.format(param=param)
    if param_with_brackets in query_dict:
        # ?foo[]=1&foo[]=2
        return query_dict.getlist(param_with_brackets)

    # ?foo[0]=1&foo[1]=2
    # может встретиться пропуск позиций: foo[0]=1&foo[2]=3&foo[3]=4
    indexed_prop_prefix = '{param}['.format(param=param)
    values = []
    for prop in query_dict.keys():
        if prop.startswith(indexed_prop_prefix):
            try:
                ix = int(prop[len(indexed_prop_prefix):].strip('[]'))
            except ValueError:
                continue

            if len(values) <= ix:
                values.extend([None] * (ix + 1 - len(values)))

            values[ix] = query_dict[prop]

    return values or default
