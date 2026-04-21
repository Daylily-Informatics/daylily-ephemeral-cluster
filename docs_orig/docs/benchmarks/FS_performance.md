# Fsx Luster vs EBS Filesystem Performance
  > Fsx is ~54x faster write than EBS based on dd... but in cat tests, EBS seems to not suffer from slow write perf. These are small tests, Fsx should be more performant from the specs, and certainly maintains performance as the FS grows and potentially thousands of clients attach to the same FS.

## Write on EBS (132MB/s)
```bash
# Running the following test 3x
dd if=/dev/zero of=tempfile bs=2M count=1024 conv=fdatasync

1024+0 records in
1024+0 records out
2147483648 bytes (2.1 GB) copied, 16.277 s, 132 MB/s
2147483648 bytes (2.1 GB) copied, 16.3091 s, 132 MB/s
2147483648 bytes (2.1 GB) copied, 16.2507 s, 132 MB/s
```

## Read on EBS (7.2GB/s)
```bash
# Running the following command 3x
dd if=tempfile of=/dev/null bs=2M count=1024
1024+0 records in
1024+0 records out
2147483648 bytes (2.1 GB) copied, 0.325774 s, 6.6 GB/s
2147483648 bytes (2.1 GB) copied, 0.290493 s, 7.4 GB/s
2147483648 bytes (2.1 GB) copied, 0.283007 s, 7.6 GB/s
```

## Write on Fsx Lustre (1.2GB/s)
```bash
# Running the following test 3x
dd if=/dev/zero of=tempfile bs=2M count=1024

1024+0 records in
1024+0 records out
2147483648 bytes (2.1 GB) copied, 1.74388 s, 1.2 GB/s
2147483648 bytes (2.1 GB) copied, 1.77259 s, 1.2 GB/s
2147483648 bytes (2.1 GB) copied, 1.78434 s, 1.2 GB/s
```

## Read on Fsx Lustre (7GB/s)
```bash
# Running the following test 3x
dd if=tempfile of=/dev/null bs=2M count=1024

1024+0 records in
1024+0 records out
2147483648 bytes (2.1 GB) copied, 0.298337 s, 7.2 GB/s
2147483648 bytes (2.1 GB) copied, 0.336512 s, 6.4 GB/s
2147483648 bytes (2.1 GB) copied, 0.292036 s, 7.4 GB/s
```

## cat 2.1G File:
  > unusual the slow read from EBS is not reflected here...
### Fsx->Fsx
  - 2.1s (avg of 3)
### Fsx->EBS
  - 1.1s (avg of 3)
### EBS->EBS
  - 1.1s (avg of 3)
### EBS->Fsx
  - 2.9s (avg of 3)
