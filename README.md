# FuzzBench Fork for Triereme Evaluation

This FuzzBench fork contains the code necessary to run all the experiments in
the paper "Triereme: Speeding up hybrid fuzzing through efficient query
scheduling". The code for the fuzzer can be found in [this][triereme]
repository.

This fork contains 8 additional fuzzers (`aflplusplus_cmplog_forkmode`,
`aflplusplus_cmplog_forkmode_double`, `symcc_libafl_single`,
`symcc_libafl_double`, `triereme_linear_single`, `triereme_linear_double`,
`triereme_trie_single`, `triereme_trie_double`).

We refer to the original [FuzzBench documentation][fuzzbench-docs] for
troubleshooting and setup customization, as it contains a detailed overview of
all the supported options.

[fuzzbench-docs]: https://google.github.io/fuzzbench/


## Preparation

FuzzBench requires only Python 3.10 and Docker to run. Since we have run our
evaluation on Ubuntu 20.04 , we recommend running on that distro as it is the
configuration we can provide support for.

You can install Docker following the instructions in the [official
documentation][docker-docs].

[docker-docs]: https://docs.docker.com/engine/install/ubuntu/

In order to install Python 3.10, use the following commands:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.10 python3.10-dev python3.10-venv libpq-dev
```

The setup can then be finished following the FuzzBench
[documentation][fuzzbench-prereq].

[fuzzbench-prereq]: https://google.github.io/fuzzbench/getting-started/prerequisites/


## Running experiments

In order to run experiments you will need a configuration file. The one we used
for our experiments is the following (adjust the paths to your machine):

```yaml
# The number of trials of a fuzzer-benchmark pair.
trials: 16

# The amount of time in seconds that each trial is run for.
# 23 hours = 23 * 60 * 60 = 82800
max_total_time: 82800

# The location of the docker registry.
# FIXME: Support custom docker registry.
# See https://github.com/google/fuzzbench/issues/777
docker_registry: gcr.io/fuzzbench

# The local experiment folder that will store most of the experiment data.
# Please use an absolute path.
experiment_filestore: /home/ubuntu/triereme-experiments/experiment-data

# The local report folder where HTML reports and summary data will be stored.
# Please use an absolute path.
report_filestore: /home/ubuntu/triereme-experiments/report-data

# Flag that indicates this is a local experiment.
local_experiment: true
```

You can then start experiments using the following command line:

```bash
PYTHONPATH=. python3 experiment/run_experiment.py \
  --experiment-config ${config_file} \
  --concurrent-builds 2 \
  --runners-cpus 32 \
  --measurers-cpus 32 \
  --experiment-name ${experiment_name} \
  --fuzzers \
      aflplusplus_cmplog_forkmode \
      symcc_libafl_single \
      triereme_linear_single \
      triereme_trie_single \
  --benchmarks ${benchmark_list[@]}
```

It is important to note that you should avoid committing more cores than the
total amount available on your machine. That command is for a machine with 64
cores. If you run out of RAM while building, you may want to reduce the
concurrent builds to 1. Make sure to use only benchmarks that are listed in the
paper, the others are not supported.


## Results analysis

Albeit graphically different from the plots in the paper, FuzzBench will
automatically generate an HTML report with coverage data.

The other data, which was used to generate the tables, can be extracted from the
experiment logs with the following two [scripts][triereme-scripts], which are
part of the fuzzer repository.

```bash
python3 ${triereme_root}/fuzzbench/extract_symcc_libafl_stats.py \
  ${experiment_filestore} ${experiment_name} ${output_dir}

python3 ${triereme_root}/fuzzbench/extract_trace_stats.py \
  ${experiment_filestore} ${experiment_name} ${output_dir}
```

Both scripts store the data extracted from the logs in a format that can be
easily processed with `pandas`. The compressed dataframes can be found in the
output folders. The experiment filestore can be on the on the local file system
or on a remote GCS bucket.

[triereme]: https://github.com/vusec/triereme
[triereme-scripts]: https://github.com/vusec/triereme/tree/main/fuzzbench

