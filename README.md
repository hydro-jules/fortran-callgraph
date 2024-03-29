## Tool to create call graphs from JULES source code

### Documentation

```bash
python callgrapher.py --help
```

```text
usage: callgrapher.py [-h] [-s SOURCE_DIR] [-b BUILD_DIR] [-e EXTENSION]
                      [-o OUTPUT_DIR] [-i IGNORE [IGNORE ...]] [-c] [-v]
                      root_callers [root_callers ...]

generate call graphs from preprocessed Fortran source code

positional arguments:
  root_callers          name(s) of the caller(s) in the algorithm to use as
                        root to call graph (use double underscore to separate
                        module and subroutine/function)

optional arguments:
  -h, --help            show this help message and exit
  -s SOURCE_DIR, --source_dir SOURCE_DIR
                        path to directory containing Fortran files to consider
                        for call graph - default to current working directory
  -b BUILD_DIR, --build_dir BUILD_DIR
                        path to directory where object files resulting from
                        compilation of Fortran files are (required for writing
                        the dependency file) - default to source directory
  -e EXTENSION, --extension EXTENSION
                        file extension for the source code (case-sensitive) -
                        default to f90
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR
                        path to directory where to save dot and pdf outputs of
                        the call graphs - default to outputs folder
  -i IGNORE [IGNORE ...], --ignore IGNORE [IGNORE ...]
                        name(s) of the callee(s) in the algorithm to ignore in
                        the call graph (use double underscore to separate
                        module and subroutine/function)
  -c, --cluster         visually gather entities into their containing modules
                        (if any)
  -v, --without_variables
                        option to not display the variables
```

### Example

```bash
python callgrapher.py 'snow_mod__snow' -s 'jules-vn6.0/srcpp'
```
