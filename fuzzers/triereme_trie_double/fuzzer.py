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
import subprocess

from fuzzers.symcc_libafl_single import fuzzer as symcc_fuzzer_single
from fuzzers.symcc_libafl_double import fuzzer as symcc_fuzzer_double


def build():
    """Build an AFL version and SymCC version of the benchmark"""
    symcc_fuzzer_double.build()


def fuzz(input_corpus, output_corpus, target_binary, use_trie=True):
    """
    Launches an instance of AFL++, as well as the Triereme helper.
    """
    target_binary_dir = os.path.dirname(target_binary)
    target_binary_name = os.path.basename(target_binary)

    cpuset = []
    if 'CPUSET' in os.environ:
        cpuset_bounds = os.environ['CPUSET'].split('-')
        cpuset = list(range(int(cpuset_bounds[0]), int(cpuset_bounds[1]) + 1))

    # Start an instance of AFL++.
    print('[run_fuzzer] Running AFL for SymCC')
    afl_flags = ['-M', 'afl']
    if cpuset:
        print(f"Binding AFL to core {cpuset[0]}.")
        afl_flags += ['-b', str(cpuset[0])]
    symcc_fuzzer_double.launch_afl_thread(input_corpus, output_corpus,
                                          target_binary, afl_flags,
                                          bool(cpuset))
    waited = symcc_fuzzer_single.wait_for_afl(output_corpus, 'afl')
    print(f'Waited {waited} s for AFL to start')

    # Start an instance of Triereme.
    # We need to ensure it uses the symbolic version of libc++.
    print('Starting the SymCC helper')
    symcc_workdir = symcc_fuzzer_single.get_symcc_build_dir(target_binary_dir)
    symcc_target_binary = os.path.join(symcc_workdir, target_binary_name)

    new_environ = os.environ.copy()
    assert new_environ['LD_LIBRARY_PATH']
    new_environ['LD_LIBRARY_PATH'] += f':{symcc_workdir}'
    new_environ['LD_PRELOAD'] = '/usr/lib/x86_64-linux-gnu/libjemalloc.so.2'
    new_environ['RUST_LOG'] = 'info'
    new_environ['RUST_BACKTRACE'] = '1'
    new_environ['AFL_MAP_SIZE'] = '2621440'

    linear_opt = ['--linear-solving=on'] if not use_trie else []
    cmd = [
        os.path.join(target_binary_dir,
                     'fuzzing_helper'), '-o', output_corpus, '-a', 'afl', '-n',
        'mine', '-f', target_binary, '--path-filtering-mode=factorizing',
        '--optimistic-unsolved=yes', '--optimistic-pruned=yes'
    ] + linear_opt + ['--', symcc_target_binary, '@@']
    if cpuset:
        print(f"Binding SymCC to core {cpuset[-1]}.")
        cmd = ['taskset', '-c', str(cpuset[-1])] + cmd
    subprocess.run(cmd, env=new_environ)
