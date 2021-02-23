## Tool to create call graphs from JULES source code

### Documentation

```bash
python callgrapher.py --help
```

```text
usage: callgrapher.py [-h] [-s SOURCE_DIR] [-e EXTENSION] [-o OUTPUT_DIR]
                      [-i IGNORE]
                      root_callers [root_callers ...]

generate call graphs from preprocessed Fortran source code

positional arguments:
  root_callers          name(s) of the caller(s) in the algorithm to use as
                        root to call graph (use double underscore to separate
                        module and subroutine/function)

optional arguments:
  -h, --help            show this help message and exit
  -s SOURCE_DIR, --source_dir SOURCE_DIR
                        path to top-level directory containing Fortran files
                        to consider for call graph - default to current
                        working directory
  -e EXTENSION, --extension EXTENSION
                        file extension for the source code (case-sensitive) -
                        default to f90
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR
                        path to directory where to save dot and pdf outputs of
                        the call graphs - default to current working directory
  -i IGNORE, --ignore IGNORE
                        name(s) of the callee(s) in the algorithm to ignore in
                        the call graph (use double underscore to separate
                        module and subroutine/function)
```

### Example

```bash
python callgrapher.py 'snow_mod__snow' -s 'jules-vn5.9/src' -i 'logging_mod__write_to_log'
```
