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

ARG parent_image
FROM $parent_image

# Avoid complaints from apt while installing packages
ARG DEBIAN_FRONTEND=noninteractive

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        > /tmp/rustup-init.sh && \
    sh /tmp/rustup-init.sh --default-toolchain 1.71 -y && \
    rm /tmp/rustup-init.sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Clone LLVM early to avoid cache invalidation
RUN git clone --branch llvmorg-12.0.0 --depth 1 \
        https://github.com/llvm/llvm-project.git /llvm_source

# Install dependencies 
RUN apt-get remove -y \
        llvm-10 && \
    apt-get update && \
    apt-get install -y \
        wget \
        llvm-11-dev \
        clang-11 \
        lld-11 \
        ninja-build \
        python2 \
        libz3-dev \
        zlib1g-dev

# Build AFL++
ARG SYNC_TIME=5
RUN mkdir /afl && cd /afl && \
    wget https://github.com/AFLplusplus/AFLplusplus/archive/refs/tags/4.05c.tar.gz \
        -O AFL++.tar.gz && \
    tar xf AFL++.tar.gz --strip-components=1 && \
    sed -i "s/\(SYNC_TIME (\)30\( \* 60 .*$\)/\1${SYNC_TIME}\2/" include/config.h && \
    unset CFLAGS && unset CXXFLAGS && \
    export LLVM_CONFIG=llvm-config-11 && \
    export NO_PYTHON=1 && export NO_NYX=1 && \
    make source-only && make -C utils/aflpp_driver && \
    cp utils/aflpp_driver/libAFLDriver.a / && \
    rm AFL++.tar.gz

# Build standalone wrapper for AFL++ fork-mode
RUN cd /llvm_source && \
    /afl/afl-clang-fast -c \
        /llvm_source/compiler-rt/lib/fuzzer/standalone/StandaloneFuzzTargetMain.c \
        -o StandaloneFuzzTargetMainAFL.o && \
    ar rc /libStandaloneFuzzTarget.a \
        StandaloneFuzzTargetMainAFL.o && \
    rm StandaloneFuzzTargetMainAFL.o

# Clone and build SymCC
ARG bust_cache=1
RUN git clone --recursive --branch triereme \
    https://github.com/vusec/symcc-triereme.git /symcc

RUN mkdir /symcc_build && cd /symcc_build && \
    unset CFLAGS && unset CXXFLAGS && \
    cmake -G Ninja \
        -DQSYM_BACKEND=ON \
        -DCMAKE_BUILD_TYPE=Release \
        -DZ3_TRUST_SYSTEM_VERSION=ON \
        /symcc && \
    ninja && \
    mkdir "$OUT/lib" && \
    cp /symcc_build/SymRuntime-prefix/src/SymRuntime-build/libSymRuntime.so "$OUT/lib" && \
    cargo build --release --manifest-path /symcc/util/symcc_fuzzing_helper/Cargo.toml && \
    cp /symcc/util/symcc_fuzzing_helper/target/release/symcc_fuzzing_helper "$OUT"

# Build standalone wrapper for SymCC
RUN cd /llvm_source && \
    /symcc_build/symcc -c \
        /llvm_source/compiler-rt/lib/fuzzer/standalone/StandaloneFuzzTargetMain.c \
        -o StandaloneFuzzTargetMainSymCC.o && \
    ar rc /libStandaloneFuzzTargetSymCC.a \
        StandaloneFuzzTargetMainSymCC.o && \
    rm StandaloneFuzzTargetMainSymCC.o

# Build libcxx with SymCC
RUN mkdir /libcxx_native_install && mkdir /libcxx_native_build && \
    cd /libcxx_native_install \
    && export SYMCC_REGULAR_LIBCXX="" && \
    cmake /llvm_source/llvm                                     \
      -G Ninja                                                  \
      -DLLVM_ENABLE_PROJECTS="libcxx;libcxxabi"                 \
      -DLLVM_DISTRIBUTION_COMPONENTS="cxx;cxxabi;cxx-headers"   \
      -DLLVM_TARGETS_TO_BUILD="X86" -DCMAKE_BUILD_TYPE=Release  \
      -DCMAKE_C_COMPILER=/symcc_build/symcc                     \
      -DCMAKE_CXX_COMPILER=/symcc_build/sym++                   \
      -DHAVE_POSIX_REGEX=1                                      \
      -DCMAKE_INSTALL_PREFIX="/libcxx_native_build"             \
      -DHAVE_STEADY_CLOCK=1 && \
    ninja distribution && \
    ninja install-distribution && \
    mkdir -p "$OUT/lib" && \
    cp /libcxx_native_build/lib/libc++.so.1 "$OUT/lib" && \
    cp /libcxx_native_build/lib/libc++abi.so.1 "$OUT/lib"
