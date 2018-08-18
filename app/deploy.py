import jinjaenv
import json


# yamlreader to merge multiple yaml files into one
def load_services(path, jinja):
    from yamlreader import yaml_load as yamlreader
    import shlex
    import subprocess
    from ruamel.yaml import YAML
    from ruamel.yaml.compat import StringIO

    files = subprocess.check_output(shlex.split('find {} -name "*.yml" -type f ! -path "*/disabled/*"'.format(path)))
    files = files.split()
    servicesTemplate = yamlreader(files, defaultdata={})
    print("\nYAML files in {}".format(path))
    from tabulate import tabulate; print(tabulate(map(lambda file: {'file': file}, files), headers={'file':'Path'}, showindex="always", tablefmt="fancy_grid"))

    #top level key: value
    values = {}
    for key, value in servicesTemplate.items():
        if key in ['namespaces', 'priorityclasses']:
            continue
        values[key] = value
    # print("\nValues")
    # from tabulate import tabulate; print(tabulate([(k,v) for k,v in values.items()], headers=['Key', 'Value'], showindex="always", tablefmt="fancy_grid"))
    # print values

    yaml=YAML()
    # yaml.default_style='"'
    yaml.default_flow_style=False
    servicesStream = StringIO()
    yaml.dump(servicesTemplate, servicesStream)
    servicesJinja = jinja.from_string(servicesStream.getvalue())
    servicesRendered = servicesJinja.render(values)
    # print(servicesRendered)
    services = yaml.load(servicesRendered)
    return services

def get_all_existing(kinds, kubectl):
    existing = dict()
    for kind in kinds:
        items = get_existing(kind, kubectl)
        for item in items:
            namespace = item['metadata'].get('namespace', '')
            name = item['metadata']['name']
            key = (namespace, kind, name)
            existing[key] = item
    return existing

def get_existing(kind, kubectl):
    existingJson = kubectl.execute('get {} -l managed=true --all-namespaces -o json'.format(kind))
    parsed = json.loads(existingJson)
    return parsed.get('items', [])

#list of processed tuples(namspace, kind, name); use for delete later
processed = set()

# general loop thru all namespaces
def process_applies(services, existing, jinja):
    applies = list()
    # priority classes are global and part of any namespaces so must be done first
    for priorityclass in services.get('priorityclasses', []):
        rendered = jinja.get_template('priorityclass.j2').render({'item': priorityclass})
        process(rendered, existing, applies)
    # todo: move crd to outside of any namespace

    # storageclass
    for storageclass in services.get('storageclasses', []):
        item = {'item': storageclass}
        rendered = jinja.get_template('storageclass.j2').render(item)
        process(rendered, existing, applies)

    for namespace in services.get('namespaces', []):
        # namespaces
        rendered = jinja.get_template('namespace.j2').render({'item': {'name': namespace}})
        process(rendered, existing, applies)

        # persistentVolumes
        for persistentVolume in services['namespaces'][namespace].get('persistentVolumes', []):
            item = {'item': persistentVolume, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('persistentvolume.j2').render(item)
            process(rendered, existing, applies)

        # persistentVolumeClaims
        for persistentVolumeClaim in services['namespaces'][namespace].get('persistentVolumeClaims', []):
            item = {'item': persistentVolumeClaim, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('persistentvolumeclaim.j2').render(item)
            process(rendered, existing, applies)

        # limits
        limits = services['namespaces'][namespace].get('limits')
        if limits:
            item = {'item': {'name': namespace, 'limits': limits}, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('limits.j2').render(item)
            process(rendered, existing, applies)

        # configmaps
        for configmap in services['namespaces'][namespace].get('configmaps', []):
            item = {'item': configmap, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('configmap.j2').render(item)
            process(rendered, existing, applies)

        # customresourcedefinitions
        # todo: crd does not belong to any namespace
        for customresourcedefinition in services['namespaces'][namespace].get('customresourcedefinitions', []):
            item = {'item': customresourcedefinition}
            rendered = jinja.get_template('customresourcedefinition.j2').render(item)
            process(rendered, existing, applies)

        # customresources
        for customresource in services['namespaces'][namespace].get('customresources', []):
            item = {'item': customresource, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('customresource.j2').render(item)
            process(rendered, existing, applies)

        # secrets
        for secret in services['namespaces'][namespace].get('secrets', []):
            item = {'item': secret, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('secret.j2').render(item)
            process(rendered, existing, applies)

        # roles
        for role in services['namespaces'][namespace].get('roles', []):
            item = {'item': role, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('role.j2').render(item)
            process(rendered, existing, applies)

        # clusterRoles
        for clusterRole in services['namespaces'][namespace].get('clusterRoles', []):
            item = {'item': clusterRole, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('clusterrole.j2').render(item)
            process(rendered, existing, applies)

        # serviceAccounts
        for serviceAccount in services['namespaces'][namespace].get('serviceAccounts', []):
            # serviceAccount
            item = {'item': serviceAccount, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('serviceaccount.j2').render(item)
            process(rendered, existing, applies)

            # role binding
            if 'roleBinding' in serviceAccount:
                item = {'item': serviceAccount, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('rolebinding.j2').render(item)
                process(rendered, existing, applies)

            # cluster role binding
            if 'clusterRoleBinding' in serviceAccount:
                item = {'item': serviceAccount, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('clusterrolebinding.j2').render(item)
                process(rendered, existing, applies)

        # podpresets
        for podpreset in services['namespaces'][namespace].get('podpresets', []):
            item = {'item': podpreset, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('podpresets.j2').render(item)
            process(rendered, existing, applies)

        # daemonsets
        for daemonset in services['namespaces'][namespace].get('daemonsets', []):
            # service accounts
            if 'roleBinding' in daemonset or 'clusterRoleBinding' in daemonset:
                item = {'item': daemonset, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('serviceaccount.j2').render(item)
                process(rendered, existing, applies)

            # role binding
            if 'roleBinding' in daemonset:
                item = {'item': daemonset, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('rolebinding.j2').render(item)
                process(rendered, existing, applies)

            # cluster role binding
            if 'clusterRoleBinding' in daemonset:
                item = {'item': daemonset, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('clusterrolebinding.j2').render(item)
                process(rendered, existing, applies)

            # daemonset
            item = {'item': daemonset, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('daemonset.j2').render(item)
            process(rendered, existing, applies)

        # services and statefulsets
        for service in services['namespaces'][namespace].get('services', []):
            # services
            item = {'item': service, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('service.j2').render(item)
            process(rendered, existing, applies)

            # network policy
            if 'networkpolicy' in service:
                item = {'item': service, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('networkpolicy.j2').render(item)
                process(rendered, existing, applies)

            # service accounts
            if 'roleBinding' in service or 'clusterRoleBinding' in service:
                item = {'item': service, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('serviceaccount.j2').render(item)
                process(rendered, existing, applies)

            # role binding
            if 'roleBinding' in service:
                item = {'item': service, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('rolebinding.j2').render(item)
                process(rendered, existing, applies)

            # cluster role binding
            if 'clusterRoleBinding' in service:
                item = {'item': service, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('clusterrolebinding.j2').render(item)
                process(rendered, existing, applies)

            # endpoints
            if 'endpoints' in service:
                item = {'item': service, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('endpoints.j2').render(item)
                process(rendered, existing, applies)

            # statefulsets
            if 'stateful' in service:
                item = {'item': service, 'namespace': {'name': namespace}}
                item['global_podpresets'] = {'spec': []}
                rendered = jinja.get_template('statefulset.j2').render(item)
                process(rendered, existing, applies)

            # deployments
            elif 'pod' in service:
                item = {'item': service, 'namespace': {'name': namespace}}
                item['global_podpresets'] = {'spec': []}
                rendered = jinja.get_template('deployment.j2').render(item)
                process(rendered, existing, applies)

            # hpa
            if 'autoscaler' in service:
                item = {'item': service, 'namespace': {'name': namespace}}
                rendered = jinja.get_template('hpa.j2').render(item)
                process(rendered, existing, applies)

        # ingresses
        for ingress in services['namespaces'][namespace].get('ingresses', []):
            item = {'item': ingress, 'namespace': {'name': namespace}}
            rendered = jinja.get_template('ingress.j2').render(item)
            process(rendered, existing, applies)

    return applies

def diff(existing, processed):
    apiVersion = processed['apiVersion']
    import re
    match = re.search('(.*)/(.*)', apiVersion)
    if match is not None:
        matchVersion = match.group(2) + '.' + match.group(1)
    else:
        matchVersion = ''

    namespace = processed['metadata'].get('namespace', 'default')
    name = processed['metadata']['name']
    kind = processed["kind"].lower()
    existingJson = kubectl.execute('-n {} get {}.{} {} -o json'.format(namespace, kind, matchVersion, name))
    parsed = json.loads(existingJson)

    from deepdiff import DeepDiff as deepdiff
    exclude_paths={
        "root['metadata']['resourceVersion']",
        "root['metadata']['uid']",
        "root['metadata']['selfLink']",
        "root['metadata']['creationTimestamp']",
        "root['spec']['template']['metadata']['creationTimestamp']",
        "root['metadata']['generation']",
        "root['status']",
        "root['metadata']['annotations']['kubectl.kubernetes.io/last-applied-configuration']",
        "root['spec']['templateGeneration']",
        "root['spec']['revisionHistoryLimit']"
    }
    diffs = deepdiff(existing, processed, ignore_order=True, exclude_paths=exclude_paths, verbose_level=2, view='tree')
    # if "root['apiVersion']" in diffs['values_changed']:
        # print 'delete {} due to apiVersion change'.format(name)
    # from pprint import pprint; pprint(diffs, indent=2)
    return diffs

def process(json_string, existing, applies):
    # print(json_string)
    try:
        parsed = json.loads(json_string)
    except Exception as e:
        print(json_string)
        raise e
    # print json.dumps(parsed, indent=2, sort_keys=True)
    namespace = parsed["metadata"].get("namespace", "")
    kind = parsed["kind"].lower()
    name = parsed["metadata"]["name"]
    key = (namespace, kind, name)
    processed.add(key)

    # _diff = diff(existing.get(key, None), parsed)
    # from tabulate import tabulate; print tabulate(_diff, headers='keys')

    applies.append({
        'key': key,
        'description': 'namespace: {}, kind: {}, name: {}'.format(namespace, kind, name),
        'json_string': json_string,
        'json': parsed
    })


def process_deletes(kinds, existing, processedKeys):
    deletes = list()
    for kind in kinds:
        for key in existing.keys():
            if key[1] == kind and key not in processedKeys:
                deletes.append({
                    'key': key,
                    'description': 'namespace: {}, kind: {}, name: {}'.format(key[0], key[1], key[2]),
                })
    return deletes

def filterOnly(target, namespaceOnly, kindOnly, nameOnly):
    filtered = target
    if namespaceOnly is not None:
        filtered = list(filter(lambda apply: apply['key'][0] == namespaceOnly or apply['key'][0] == '', filtered))
    if kindOnly is not None:
        filtered = list(filter(lambda apply: apply['key'][1] == kindOnly , filtered))
    if nameOnly is not None:
        filtered = list(filter(lambda apply: apply['key'][2] == nameOnly, filtered))
    return filtered

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-s", "--namespace", dest="namespaceOnly",
                  help="limit to namespace NAMESPACE", metavar="NAMESPACE")
    parser.add_option("-k", "--kind", dest="kindOnly",
                  help="limit to kind KIND", metavar="KIND")
    parser.add_option("-n", "--name", dest="nameOnly",
                  help="limit to name NAME", metavar="NAME")
    parser.add_option("--kubeconfig", dest="kubeconfig", default="kubeconfig",
                  help="path of kubeconfig", metavar="KUBECONFIG")
    parser.add_option("--dry-run", dest="dry_run", action="store_true", default=False,
                  help="don't make any changes")
    parser.add_option("-V", "--version", dest="version", action="store_true", default=False,
                  help="print version and exit")

    (options, args) = parser.parse_args()

    # options
    namespaceOnly = options.namespaceOnly
    kindOnly = options.kindOnly
    nameOnly = options.nameOnly
    kubeconfig = options.kubeconfig

    # args
    path = args[0] if args else '.'

    if(options.version):
        import sys
        print('python version: ' + sys.version)
        import ruamel.yaml
        print('ruamel version: ' + ruamel.yaml.__version__)
        import jinja2
        print('jinja2 version: ' + jinja2.__version__)
        from kubectl import KubeCtl
        kubectl = KubeCtl(bin='kubectl')
        print(kubectl.execute('version --client --short'))
        return 0

    # jinja
    jinja = jinjaenv.setupJinja(path)

    # load services from files
    services = load_services(path, jinja)

    # kubectl cli wrapper
    from kubectl import KubeCtl
    kubectl = KubeCtl(bin='kubectl', global_flags=('--kubeconfig {}'.format(kubeconfig) if kubeconfig else ''))

    # set of supported kinds
    kindsDeletable = [
        'ingress',
        'hpa',
        'service',
        'deployment',
        'statefulset',
        'daemonset',
        'customresourcedefinition',
        'configmap',
        'podpreset',
        'rolebinding',
        'role',
        'clusterrolebinding',
        'clusterrole',
        'serviceaccount',
        'secret',
        'networkpolicy',
        'storageclass'
    ]
    kindsNonDeletable = [
        'priorityclass',
        'namespace',
        'persistentvolume',
        'persistentvolumeclaim',
        'limits',
        'endpoints',
    ]
    kinds = kindsDeletable + kindsNonDeletable
    if kindOnly is not None:
        kinds = list(filter(lambda kind: kind == kindOnly, kinds))

    # get live resources from kubernetes
    existing = get_all_existing(kinds, kubectl)

    # compute what to apply
    applies = process_applies(services, existing, jinja)
    filteredApplies = filterOnly(applies, namespaceOnly, kindOnly, nameOnly)

    # compute what to delete
    deletes = process_deletes(kindsDeletable, existing, processed)
    filteredDeletes = filterOnly(deletes, namespaceOnly, kindOnly, nameOnly)

    # display and confirm
    from tabulate import tabulate
    if len(filteredApplies):
        print('\nApplies Planned')
        print(tabulate(map(lambda each: each['key'], filteredApplies), headers=['Namespace', 'Kind', 'Name'], showindex='always', tablefmt="fancy_grid"))
    if len(filteredDeletes):
        print('\nDeletes Planned')
        print(tabulate(map(lambda each: each['key'], filteredDeletes), headers=['Namespace', 'Kind', 'Name'], showindex='always', tablefmt="fancy_grid"))

    for each in filteredApplies:
        # print json.dumps(each['json'], indent=2, sort_keys=True)
        # from ruamel.yaml import YAML
        # import sys
        # yaml=YAML(typ='safe')
        # yaml.default_flow_style=False
        # yaml.dump(each['json'], sys.stdout)
        if not options.dry_run:
            json_string = each['json_string']
            print(kubectl.apply(json_string))

    for each in filteredDeletes:
        if not options.dry_run:
            key = each['key']
            print(kubectl.execute('-n "{}" delete {} {}'.format(key[0], key[1], key[2])))

if __name__ == "__main__":
    main()
