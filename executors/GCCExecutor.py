import os
import subprocess

try:
    from cptbox import CHROOTSecurity, SecurePopen, PIPE
except ImportError:
    CHROOTSecurity, SecurePopen, PIPE = None, None, None
    from wbox import WBoxPopen

from error import CompileError
from .utils import test_executor
from .resource_proxy import ResourceProxy
from .base_executor import CompiledExecutor
from judgeenv import env

C_FS = ['.*\.so', '/proc/meminfo', '/dev/null']
GCC_ENV = env['runtime'].get('gcc_env', {})
GCC_COMPILE = os.environ.copy()

if os.name == 'nt':
    GCC_COMPILE.update((k.encode('mbcs'), v.encode('mbcs')) for k, v in
                       env['runtime'].get('gcc_compile', GCC_ENV).iteritems())
    GCC_ENV = dict((k.encode('mbcs'), v.encode('mbcs')) for k, v in GCC_ENV.iteritems())
else:
    GCC_COMPILE.update(env['runtime'].get('gcc_compile', {}))


class GCCExecutor(CompiledExecutor):
    defines = []
    flags = []
    name = 'GCC'

    def create_files(self, problem_id, main_source, aux_sources=None, fds=None, writable=(1, 2)):
        if not aux_sources:
            aux_sources = {}
        aux_sources[problem_id + self.ext] = main_source
        sources = []
        for name, source in aux_sources.iteritems():
            if '.' not in name:
                name += self.ext
            with open(self._file(name), 'wb') as fo:
                fo.write(source)
            sources.append(name)
        self.sources = sources
        self._fds = fds
        self._writable = writable

    def get_ldflags(self):
        if os.name == 'nt':
            return ['-Wl,--stack,67108864']
        return []

    def get_executable_ext(self):
        return ['', '.exe'][os.name == 'nt']

    def get_flags(self):
        return self.flags

    def get_defines(self):
        defines = ['-DONLINE_JUDGE'] + self.defines
        if os.name == 'nt':
            defines.append('-DWIN32')
        return defines

    def get_compile_args(self):
        return ([self.command, '-Wall'] + self.sources + self.get_defines() + ['-O2', '-lm', '-march=native']
               + self.get_flags() + self.get_ldflags() + ['-s', '-o', self.get_compiled_file()])

    def get_compile_env(self):
        return GCC_COMPILE

    def get_fs(self):
        return ['.*\.so', '/proc/meminfo', '/dev/null']

    def get_security(self):
        return CHROOTSecurity(self.get_fs(), writable=self._writable)

    def get_env(self):
        return GCC_ENV


def make_executor(code, command, args, ext, test_code, _defines=None):
    class Executor(ResourceProxy):
        def __init__(self, problem_id, main_source, aux_sources=None, fds=None, writable=(1, 2)):
            super(Executor, self).__init__()
            if not aux_sources:
                aux_sources = {}
            aux_sources[problem_id + ext] = main_source
            sources = []
            for name, source in aux_sources.iteritems():
                if '.' not in name:
                    name += ext
                with open(self._file(name), 'wb') as fo:
                    fo.write(source)
                sources.append(name)
            defines = ['-DONLINE_JUDGE']
            if _defines:
                defines.extend(_defines)

            if os.name == 'nt':
                compiled_extension = '.exe'
                linker_options = ['-Wl,--stack,67108864']
                defines.append('-DWIN32')
            else:
                compiled_extension = ''
                linker_options = []

            output_file = self._file('%s%s' % (problem_id, compiled_extension))
            gcc_args = ([env['runtime'][command], '-Wall'] + sources + defines + ['-O2', '-lm', '-march=native']
                       + args + linker_options + ['-s', '-o', output_file])

            gcc_process = subprocess.Popen(gcc_args, stderr=subprocess.PIPE, executable=env['runtime'][command],
                                           cwd=self._dir, env=GCC_COMPILE)
            _, compile_error = gcc_process.communicate()
            if gcc_process.returncode != 0:
                raise CompileError(compile_error)
            self._executable = output_file
            self.name = problem_id
            self._fds = fds
            self._writable = writable
            self.warning = compile_error

        if SecurePopen is None:
            def launch(self, *args, **kwargs):
                return WBoxPopen([self.name] + list(args), executable=self._executable,
                                 time=kwargs.get('time'), memory=kwargs.get('memory'),
                                 cwd=self._dir, env=GCC_ENV, network_block=True)
        else:
            def launch(self, *args, **kwargs):
                return SecurePopen([self.name] + list(args),
                                   executable=self._executable,
                                   security=CHROOTSecurity(C_FS, writable=self._writable),
                                   time=kwargs.get('time'),
                                   memory=kwargs.get('memory'),
                                   stderr=(PIPE if kwargs.get('pipe_stderr', False) else None),
                                   env=GCC_ENV,
                                   cwd=self._dir, fds=self._fds)

        def launch_unsafe(self, *args, **kwargs):
            return subprocess.Popen([self.name] + list(args),
                                    executable=self._executable,
                                    env=GCC_ENV,
                                    cwd=self._dir,
                                    **kwargs)

    def initialize():
        if command not in env['runtime']:
            return False
        if not os.path.isfile(env['runtime'][command]):
            return False
        return test_executor(code, Executor, test_code)

    return Executor, initialize