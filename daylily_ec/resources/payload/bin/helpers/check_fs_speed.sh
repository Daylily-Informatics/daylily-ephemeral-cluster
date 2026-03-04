#!/bin/bash

echo "create a 4G file, 3x"
dd if=/dev/zero of=testfile1 bs=4M count=1000
dd if=/dev/zero of=testfile2 bs=4M count=1000
dd if=/dev/zero of=testfile3 bs=4M count=1000



echo "Time reading the file from disk"
dd if=testfile1 of=/dev/null bs=4M count=1000
dd if=testfile2 of=/dev/null bs=4M count=1000
dd if=testfile3 of=/dev/null bs=4M count=1000


