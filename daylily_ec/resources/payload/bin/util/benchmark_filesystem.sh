#!/bin/env bash

# might need sudo apt install fio

filesys=$1

echo "Benchmarking /dev/shm (RAM disk)..."
fio --name=ramdisk-test --directory=$1 \
    --size=1G --rw=readwrite --bs=1M \
    --numjobs=16 --iodepth=32 --group_reporting
