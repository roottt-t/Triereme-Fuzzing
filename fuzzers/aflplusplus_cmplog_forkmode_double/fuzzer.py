# Copyright 2020 Google LLC
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
"""Integration code for AFLplusplus fuzzer."""

# This optimized afl++ variant should always be run together with
# "aflplusplus" to show the difference - a default configured afl++ vs.
# a hand-crafted optimized one. afl++ is configured not to enable the good
# stuff by default to be as close to vanilla afl as possible.
# But this means that the good stuff is hidden away in this benchmark
# otherwise.

import threading
import os

from fuzzers.aflplusplus import fuzzer as aflplusplus_fuzzer


def build():  # pylint: disable=too-many-branches,too-many-statements
    """Build benchmark."""
    aflplusplus_fuzzer.build('tracepc', 'cmplog', 'eclipser')


def launch_afl_thread(input_corpus, output_corpus, target_binary,
                      additional_flags, allow_binding):
    """ Simple wrapper for running AFL. """
    afl_thread = threading.Thread(target=aflplusplus_fuzzer.fuzz,
                                  args=(input_corpus, output_corpus,
                                        target_binary, additional_flags),
                                  kwargs={
                                      'fork_mode': True,
                                      'no_affinity': not allow_binding
                                  })
    afl_thread.start()
    return afl_thread


def fuzz(input_corpus, output_corpus, target_binary):
    """Run fuzzer."""

    cpuset = []
    if 'CPUSET' in os.environ:
        cpuset_bounds = os.environ['CPUSET'].split('-')
        cpuset = list(range(int(cpuset_bounds[0]), int(cpuset_bounds[1]) + 1))

    print('[run_fuzzer] Running secondary AFL++')
    afl_flags = ['-S', 'secondary']
    if cpuset:
        print(f"Binding secondary AFL++ to core {cpuset[1]}.")
        afl_flags += ['-b', str(cpuset[1])]
    launch_afl_thread(input_corpus, output_corpus, target_binary, afl_flags, bool(cpuset))

    print('[run_fuzzer] Running main AFL++')
    afl_flags = ['-M', 'main']
    if cpuset:
        print(f"Binding main AFL++ to core {cpuset[0]}.")
        afl_flags += ['-b', str(cpuset[0])]
    aflplusplus_fuzzer.fuzz(input_corpus,
                            output_corpus,
                            target_binary,
                            flags=afl_flags,
                            fork_mode=True,
                            no_affinity=not bool(cpuset))
