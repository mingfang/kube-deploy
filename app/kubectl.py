import json
import logging
from subprocess import CalledProcessError, check_output, Popen, PIPE
import shlex

class KubeCtl(object):
    def __init__(self, bin='kubectl', global_flags=''):
        super(KubeCtl, self).__init__()
        self.kubectl = '{} {}'.format(bin, global_flags)

    def execute(self, command, definition=None, safe=False, dry_run=False):
        cmd = '{} {}'.format(self.kubectl, command)

        try:
            if definition:
                pre = 'echo \'{}\''.format(definition)
                cmd = '{} -f -'.format(cmd)
                cmd_process = Popen(shlex.split(cmd), stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf8')
                print(cmd)
                output,error = cmd_process.communicate(input=definition)
                if error:
                    print(error)
                    raise CalledProcessError(cmd_process.returncode, '{} | {}'.format(pre, cmd))
                return output
            else:
                print(cmd)
                return check_output(shlex.split(cmd))
        except CalledProcessError as e:
            if not safe:
                raise e
            logging.warn('Command {} failed, swallowing'.format(command))

    def apply(self, *args, **kwargs):
        return self.execute('apply', *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.execute('delete', *args, **kwargs)

    def get(self, *args, **kwargs):
        result = self.execute('get -a -o json', *args, **kwargs).decode()
        return json.loads(result)['items']

    def describe(self, *args, **kwargs):
        return self.execute('describe', *args, **kwargs)