def setupJinja(path):
    from jinja2 import Environment, FileSystemLoader, PackageLoader
    env = Environment(
        trim_blocks=True,
        loader=PackageLoader(__name__)
    )

    # jinja2 filters copied from ansible
    import re
    def regex_replace(value='', pattern='', replacement='', ignorecase=False):
        ''' Perform a `re.sub` returning a string '''

        # value = to_text(value, errors='surrogate_or_strict', nonstring='simplerepr')

        if ignorecase:
            flags = re.I
        else:
            flags = 0
        _re = re.compile(pattern, flags=flags)
        return _re.sub(replacement, value)
    env.filters['regex_replace'] = regex_replace

    import collections
    def unique(a):
        if isinstance(a, collections.Hashable):
            c = set(a)
        else:
            c = []
            for x in a:
                if x not in c:
                    c.append(x)
        return c
    def union(a, b):
        if isinstance(a, collections.Hashable) and isinstance(b, collections.Hashable):
            c = set(a) | set(b)
        else:
            c = unique(a + b)
        return c
    env.filters['union'] = union

    import sys
    PY3 = sys.version_info[0] == 3
    if PY3:
        def iteritems(d, **kw):
            return iter(d.items(**kw))
    else:
        def iteritems(d, **kw):
            return d.iteritems(**kw)

    import itertools
    from collections import MutableMapping
    def combine(*terms, **kwargs):
        recursive = kwargs.get('recursive', False)
        if len(kwargs) > 1 or (len(kwargs) == 1 and 'recursive' not in kwargs):
            raise Error("'recursive' is the only valid keyword argument")

        dicts = []
        for t in terms:
            if isinstance(t, MutableMapping):
                dicts.append(t)
            elif isinstance(t, list):
                dicts.append(combine(*t, **kwargs))
            else:
                raise Error("|combine expects dictionaries, got " + repr(t))

        if recursive:
            return reduce(merge_hash, dicts)
        else:
            return dict(itertools.chain(*map(iteritems, dicts)))
    env.filters['combine'] = combine

    import json
    def to_json(a, *args, **kw):
        ''' Convert the value to JSON '''
        return json.dumps(a, *args, **kw)
    env.filters['to_json'] = to_json

    return env

