# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
''' Uses the SymCC-AFL hybrid from SymCC. '''

import os
import time
import threading
import subprocess

from fuzzers import utils
from fuzzers.aflplusplus import fuzzer as aflplusplus_fuzzer


def get_symcc_build_dir(target_directory):
    """Return path to symcc target directory."""
    return os.path.join(target_directory, 'symcc')


def build():
    """Build an AFL version and SymCC version of the benchmark"""

    old_env = os.environ.copy()

    print('Building with AFL++ and CMPLOG')
    src = os.getenv('SRC')
    work = os.getenv('WORK')

    with utils.restore_directory(src), utils.restore_directory(work):
        # Restore SRC to its initial state so we can build again without any
        # trouble. For some OSS-Fuzz projects, build_benchmark cannot be run
        # twice in the same directory without this.
        aflplusplus_fuzzer.build('tracepc', 'cmplog', 'eclipser')
    os.environ = old_env.copy()

    print('Building with SymCC')
    symcc_build_dir = get_symcc_build_dir(os.environ['OUT'])
    os.mkdir(symcc_build_dir)

    # Set flags to ensure compilation with SymCC.
    new_env = old_env.copy()
    new_env['CC'] = '/symcc_build/symcc'
    new_env['CXX'] = '/symcc_build/sym++'
    new_env['CXXFLAGS'] += ' -ldl -nostdinc++'
    new_env['FUZZER_LIB'] = '/libStandaloneFuzzTargetSymCC.a'
    new_env['OUT'] = symcc_build_dir

    new_env['CXXFLAGS'] += ' -fno-sanitize=all '
    new_env['CFLAGS'] += ' -fno-sanitize=all '

    # Setting this environment variable instructs SymCC to use the
    # libcxx library compiled with SymCC instrumentation.
    new_env['SYMCC_LIBCXX_PATH'] = '/libcxx_native_build'

    # Instructs SymCC to consider no symbolic inputs at runtime. This is needed
    # if, for example, some tests are run during compilation of the benchmark.
    new_env['SYMCC_NO_SYMBOLIC_INPUT'] = '1'

    utils.build_benchmark(env=new_env)


def launch_afl_thread(input_corpus, output_corpus, target_binary,
                      additional_flags):
    """ Simple wrapper for running AFL. """
    afl_thread = threading.Thread(target=aflplusplus_fuzzer.fuzz,
                                  args=(input_corpus, output_corpus,
                                        target_binary, additional_flags),
                                  kwargs={'fork_mode': True})
    afl_thread.start()
    return afl_thread


def wait_for_afl(output_corpus, afl_instance_name, timeout=5 * 60):
    fuzzer_stats_path = os.path.join(output_corpus, afl_instance_name,
                                     'fuzzer_stats')

    waited = 0
    while not os.path.isfile(fuzzer_stats_path):
        time.sleep(5)
        waited += 5

        if waited > 120:
            raise Exception('Timeout while waiting for AFL')

    return waited


def fuzz(input_corpus, output_corpus, target_binary):
    """
    Launches an instance of AFL++, as well as the SymCC helper.
    """
    target_binary_dir = os.path.dirname(target_binary)
    target_binary_name = os.path.basename(target_binary)

    # Start an instance of AFL++.
    print('[run_fuzzer] Running AFL for SymCC')
    launch_afl_thread(input_corpus, output_corpus, target_binary, ['-M', 'afl'])
    waited = wait_for_afl(output_corpus, 'afl')
    print(f'Waited {waited} s for AFL to start')

    # Start an instance of SymCC.
    # We need to ensure it uses the symbolic version of libc++.
    print('Starting the SymCC helper')
    symcc_workdir = get_symcc_build_dir(target_binary_dir)
    symcc_target_binary = os.path.join(symcc_workdir, target_binary_name)

    new_environ = os.environ.copy()
    assert new_environ['LD_LIBRARY_PATH']
    new_environ['LD_LIBRARY_PATH'] += f':{symcc_workdir}'
    new_environ['RUST_BACKTRACE'] = '1'
    new_environ['AFL_MAP_SIZE'] = '2621440'
    cmd = [
        os.path.join(target_binary_dir,
                     'symcc_fuzzing_helper'), '-o', output_corpus, '-a', 'afl',
        '-n', 'symcc', '-f', target_binary, '--', symcc_target_binary, '@@'
    ]
    subprocess.run(cmd, env=new_environ)
