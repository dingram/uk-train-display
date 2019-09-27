#!/bin/bash

set -eu
export TZ="${TZ:-Europe/London}"


function main() {
  exec python ./src/main.py --emulate_display "$@"
}


main "$@"
