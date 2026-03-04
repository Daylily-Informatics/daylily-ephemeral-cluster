#!/bin/bash

watch 'sinfo && squeue -o "%.18i %.8u %.8T %.10M %.30N %.50j" '
