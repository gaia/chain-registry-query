## Chain Registry Query Tool

### Description
This is a command-line utility for querying the [Cosmos Chain Registry](https://github.com/cosmos/chain-registry/ "Cosmos Chain Registry") to test the listed resources for liveliness. The live results are then sorted by ping time on lowest latency to your location. The failed resources are also listed, along with the reason for failure.

[![Help](https://i.imgur.com/qHnHcwH.png "Help")](https://i.imgur.com/qHnHcwH.png "Help")

### Dependencies
- requests
- ping3
- prettytable

Already available by default:
- telnetlib
- argparse
- json
- sys
- os


### Usage Example
usage: chain-registry-query.py [-h] [--max_results MAX_RESULTS] [--polkachu] [--no_fileout] chain type

**positional arguments**:
-   `chain`                 the name of the chain
-   `type`                  the type of peers (persistent_peers, seeds, rpc, rest, grpc)

**optional**:
-   `-h, --help`            show this help message and exit
-   `--max_results MAX_RESULTS`       the maximum number of results to display (still tests all results)
-   `--polkachu`            use the polkachu API instead of the registry
-   `--no_fileout`          do not write successful seeds and persistent_peers results to a file

### To install
`pip install -r requirements.txt`
