from .base_executor import CompiledExecutor
from dmoj.conf import env


class Executor(CompiledExecutor):
    ext = '.coffee'
    name = 'COFFEE'
    fs = ['.*\.so', '/usr/', '/etc/localtime$', '/dev/null$']
    command = env['runtime'].get('chicken-csc')
    syscalls = ['getpid', 'getppid', 'clock_getres', 'timer_create', 'timer_settime',
                'timer_delete', 'newselect', 'select']
    test_program = '(declare (uses extras)) (map print (read-lines))'

    def get_compile_args(self):
        return [self.get_command(), self._code]


initialize = Executor.initialize