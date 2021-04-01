from glob import glob
from os import sep
import re
import csv
import graphviz as gv
import argparse


_intrinsic_fortran = [
    'iso_fortran_env',
    'iso_c_binding',
    'omp_lib',
    'omp_lib_kinds',
    'get_command_argument',
    'random_number',
    'random_seed'
]

# priorities to give in compilation to avoid missing dependencies
# (keys are the priorities, optional values are lower-order priorities
#  that need to be checked because the key name is included in the name
#  of the value and could trigger a false positive)
_priorities = {
    'drhook_dummy': None,
    'mpi_dummy': None,
    'netcdf_dummy': None,
    'params': 'science/params',
    'util': None,
    'io': None,
    'control': None,
    'initialisation': None,
    'science/params': None,
    'science': None
}


def parse_fortran_files(fortran_files, sep_):
    # parse files
    locations = {}
    caller_callees = {}
    memberships = {}
    kinds = {}

    for fortran_file in fortran_files:
        # internal subroutines and functions
        internal = []
        # variable or subroutine/function renaming using '=>'
        renaming = {}
        # store name of modules from use to append in call
        use_to_call = {}
        # to know if we are in an interface block
        in_interface = False
        # to unwrap wrapped lines using '&'
        line_continued = ''
        # to store current location in tree view
        breadcrumbs = []

        # first pass to find out which functions/subroutines are internal
        with open(fortran_file, 'r') as f:
            for i, line in enumerate(f):
                # ignore commented lines
                if line.strip().startswith('!') or line.strip().startswith('#'):
                    continue

                # unwrap continued lines
                if line.strip().endswith('&'):
                    line_continued += ' ' + line.strip()[:-1]
                    continue
                elif line_continued:
                    line = line_continued + ' ' + line.strip()
                    line_continued = ''

                # eliminate inline comments
                if '!' in line:
                    line = line.split('!')[0]

                # find subroutines
                if re.search(r"(SUBROUTINE +)([0-9A-Za-z_]+)", line):
                    internal.append(re.search(r"(SUBROUTINE +)([0-9A-Za-z_]+)", line).group(2).lower())
                # find functions
                elif re.search(r"(FUNCTION +)([0-9A-Za-z_]+)", line):
                    internal.append(re.search(r"(FUNCTION +)([0-9A-Za-z_]+)", line).group(2).lower())

        # second pass to properly parse the file
        with open(fortran_file, 'r') as f:
            for i, line in enumerate(f):
                lineno = i + 1

                # ignore commented lines
                if line.strip().startswith('!') or line.strip().startswith('#'):
                    continue

                # unwrap continued lines
                if line.strip().endswith('&'):
                    line_continued += ' ' + line.strip()[:-1]
                    continue
                elif line_continued:
                    line = line_continued + ' ' + line.strip()
                    line_continued = ''

                # eliminate inline comments
                if '!' in line:
                    line = line.split('!')[0]

                # find interfaces
                if re.search(r"(END +INTERFACE *)([0-9A-Za-z_]*)", line):
                    name = re.search(r"(END +INTERFACE *)([0-9A-Za-z_]*)", line).group(2).lower()
                    if not in_interface:
                        raise RuntimeError("'END INTERFACE' found without 'INTERFACE': "
                                           "{} in {} #L{}".format(name, fortran_file, lineno))
                    else:
                        in_interface = False
                elif in_interface in ['operator', 'assignment', 'generic']:
                    # ignore these type of interfaces
                    continue
                elif re.search(r"(INTERFACE +)(operator *\()", line):
                    # ignore interface since overloaded operator on type
                    in_interface = 'operator'
                elif re.search(r"(INTERFACE +)(assignment *\()", line):
                    # ignore interface since overloaded assignment on type
                    in_interface = 'assignment'
                elif re.search(r"(INTERFACE +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(INTERFACE +)([0-9A-Za-z_]+)", line).group(2).lower()
                    if breadcrumbs:
                        if breadcrumbs[-1] not in memberships:
                            memberships[breadcrumbs[-1]] = []
                        memberships[breadcrumbs[-1]].append(name)
                    kinds[sep_.join(breadcrumbs + [name])] = 'GENERIC_INTERFACE'
                    locations[sep_.join(breadcrumbs + [name])] = fortran_file
                    # ignore interface since also defined elsewhere
                    in_interface = 'generic'
                elif re.search(r"(INTERFACE *)", line):
                    # proceed as if not in an interface
                    in_interface = 'explicit'

                # find programs
                if re.search(r"(END +PROGRAM +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(END +PROGRAM +)([0-9A-Za-z_]+)", line).group(2).lower()
                    if breadcrumbs and (name == breadcrumbs[-1]):
                        breadcrumbs.pop(-1)
                        if breadcrumbs:
                            raise RuntimeError("'PROGRAM' closed but remainder: "
                                               "{} in {} #L{}".format(name, fortran_file, lineno))
                    else:
                        raise RuntimeError("'END PROGRAM' found without 'program': "
                                           "{} in {} #L{}".format(name, fortran_file, lineno))
                elif re.search(r"(PROGRAM +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(PROGRAM +)([0-9A-Za-z_]+)", line).group(2).lower()
                    breadcrumbs.append(name)
                    kinds[sep_.join(breadcrumbs)] = 'PROGRAM'
                    locations[sep_.join(breadcrumbs)] = fortran_file

                # find modules
                elif re.search(r"(END +MODULE +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(END +MODULE +)([0-9A-Za-z_]+)", line).group(2).lower()
                    if breadcrumbs and (name == breadcrumbs[-1]):
                        breadcrumbs.pop(-1)
                        if breadcrumbs:
                            raise RuntimeError("'MODULE' closed but remainder: "
                                               "{} in {} #L{}".format(name, fortran_file, lineno))
                    else:
                        raise RuntimeError("'END MODULE' found without 'MODULE': "
                                           "{} in {} #L{}".format(name, fortran_file, lineno))
                elif re.search(r"(MODULE +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(MODULE +)([0-9A-Za-z_]+)", line).group(2).lower()
                    breadcrumbs.append(name)
                    kinds[sep_.join(breadcrumbs)] = 'MODULE'
                    locations[sep_.join(breadcrumbs)] = fortran_file

                # find types
                elif re.search(r"(END +TYPE +)([0-9A-Za-z_]*)", line):
                    name = re.search(r"(END +TYPE *)([0-9A-Za-z_]*)", line).group(2).lower()
                    if breadcrumbs and (name == breadcrumbs[-1]):
                        breadcrumbs.pop(-1)
                    else:
                        raise RuntimeError("'END TYPE' found without 'TYPE': "
                                           "{} in {} #L{}".format(name, fortran_file, lineno))

                elif re.search(r"(TYPE +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(TYPE +)([0-9A-Za-z_]+)", line).group(2).lower()
                    if breadcrumbs:
                        if breadcrumbs[-1] not in memberships:
                            memberships[breadcrumbs[-1]] = []
                        memberships[breadcrumbs[-1]].append(name)
                    breadcrumbs.append(name)
                    kinds[sep_.join(breadcrumbs)] = 'TYPE'
                    locations[sep_.join(breadcrumbs)] = fortran_file

                # find subroutines
                elif re.search(r"(END +SUBROUTINE +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(END +SUBROUTINE +)([0-9A-Za-z_]+)", line).group(2).lower()
                    if breadcrumbs and (name == breadcrumbs[-1]):
                        breadcrumbs.pop(-1)
                    else:
                        raise RuntimeError("'END SUBROUTINE' found without 'SUBROUTINE': "
                                           "{} in {} #L{}".format(name, fortran_file, lineno))
                elif re.search(r"(SUBROUTINE +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(SUBROUTINE +)([0-9A-Za-z_]+)", line).group(2).lower()
                    if breadcrumbs:
                        if breadcrumbs[-1] not in memberships:
                            memberships[breadcrumbs[-1]] = []
                        memberships[breadcrumbs[-1]].append(name)
                    breadcrumbs.append(name)
                    kinds[sep_.join(breadcrumbs)] = 'SUBROUTINE'
                    locations[sep_.join(breadcrumbs)] = fortran_file

                # find functions
                elif re.search(r"(END +FUNCTION +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(END +FUNCTION +)([0-9A-Za-z_]+)", line).group(2).lower()
                    if breadcrumbs and (name == breadcrumbs[-1]):
                        breadcrumbs.pop(-1)
                    else:
                        raise RuntimeError("'END FUNCTION' found without 'FUNCTION': "
                                           "{} in {} #L{}".format(name, fortran_file, lineno))
                elif re.search(r"(FUNCTION +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(FUNCTION +)([0-9A-Za-z_]+)", line).group(2).lower()
                    if breadcrumbs:
                        if breadcrumbs[-1] not in memberships:
                            memberships[breadcrumbs[-1]] = []
                        memberships[breadcrumbs[-1]].append(name)
                    breadcrumbs.append(name)
                    kinds[sep_.join(breadcrumbs)] = 'FUNCTION'
                    locations[sep_.join(breadcrumbs)] = fortran_file

                # find use statements
                elif re.search(
                        r"(USE +)([0-9A-Za-z_]+)( *, *ONLY *:)([0-9A-Za-z_,+\-*/=><() ]+)", line):
                    match = re.search(r"(USE +)([0-9A-Za-z_]+)( *, *ONLY *:)([0-9A-Za-z_,+\-*/=><() ]+)", line)
                    for name in match.group(4).lower().split(','):
                        name = name.strip()
                        if name:
                            if sep_.join(breadcrumbs) not in caller_callees:
                                caller_callees[sep_.join(breadcrumbs)] = []
                            if '=>' in name:
                                name1, name2 = name.split('=>')
                                caller_callees[sep_.join(breadcrumbs)].append(
                                    sep_.join([match.group(2).lower(), name2.strip()])
                                )
                                # store renaming
                                renaming[name1.strip()] = name2.strip()
                                # store module name
                                use_to_call[name1.strip()] = match.group(2).lower()
                            else:
                                caller_callees[sep_.join(breadcrumbs)].append(
                                    sep_.join([match.group(2).lower(), name])
                                )
                                # store module name
                                use_to_call[name] = match.group(2).lower()

                # find call statements
                elif re.search(r"(CALL +)([0-9A-Za-z_]+)", line):
                    name = re.search(r"(CALL +)([0-9A-Za-z_]+)", line).group(2).lower()
                    # determine belonging of callee
                    if name in use_to_call:
                        # it is within another namespace in another file
                        root = use_to_call[name]
                    elif name in internal:
                        if breadcrumbs:
                            # it is within the namespace in the given file
                            # (assuming only one namespace per file, which
                            #  seems to be a reasonable assumption for JULES)
                            root = breadcrumbs[0]
                        else:
                            # it is in the given file outside any namespace
                            root = ''
                    else:
                        # it is in another file outside any namespace
                        root = ''
                    # rename if required
                    if name in renaming:
                        name = renaming[name]
                    if sep_.join(breadcrumbs) not in caller_callees:
                        caller_callees[sep_.join(breadcrumbs)] = []
                    caller_callees[sep_.join(breadcrumbs)].append(
                        sep_.join([root, name]) if root else name
                    )
                    # add call to subroutine kind (even if it may
                    # already be in there, this makes sure calls to
                    # external modules are picked up)
                    kinds[sep_.join([root, name]) if root else name] = 'SUBROUTINE'

    return caller_callees, memberships, kinds, locations


def generate_dot_and_pdf(root_caller, caller_callees, memberships, kinds,
                         sep_, out_dir, ignore=None, clustering=False,
                         without_variables=False):
    # formatting
    node_attrs = {
        'PROGRAM': {
            'shape': 'parallelogram',
            'style': 'filled',
            'fillcolor': 'grey'
        },
        'MODULE': {
            'style': 'filled',
            'fillcolor': 'grey'
        },
        'SUBROUTINE': {
            'style': 'filled',
            'fillcolor': 'transparent'
        },
        'FUNCTION': {
            'style': 'filled',
            'fillcolor': 'transparent'
        },
        # generic interface assimilated as subroutine/function
        'GENERIC_INTERFACE': {
            'style': 'filled',
            'fillcolor': 'transparent'
        },
        'TYPE': {
            'style': 'rounded',
            'fillcolor': 'transparent'
        },
        'VARIABLE': {
            'style': 'diagonals',
            'fillcolor': 'transparent'
        }
    }

    graph_attrs = {
        'engine': 'dot',
        'graph_attr': {
            'rankdir': 'LR',
            'style': 'dotted'
        },
        # default edge
        'edge_attr': {
            'dir': 'both',
            'arrowhead': 'normal',
            'arrowtail': 'none'
        },
        # default node
        'node_attr': {
            'shape': 'box',
            'fontname': 'Helvetica'
        }
    }

    # create graph
    base = gv.Digraph(name='base', **graph_attrs)

    # get initial caller
    callers = [root_caller]

    # start graph construction
    graphs = {}
    nodes = []
    edges = []
    ext_caller_callers = {}

    while callers:
        next_callers = []
        for caller in callers:
            # if caller not already a node, make it one
            if caller not in nodes:
                if caller not in kinds:
                    # i.e. it is a variable
                    if without_variables:
                        continue

                # split up parent and child in caller if possible
                if sep_ in caller:
                    parent, child = caller.split(sep_)
                    if parent not in nodes:
                        # create cluster graph if requested
                        if clustering:
                            graph = gv.Digraph(
                                name='_'.join(['cluster', parent]),
                                **graph_attrs
                            )
                        else:
                            graph = base
                        graphs[parent] = graph
                        # add node for parent
                        graph.node(parent, **node_attrs[kinds.get(parent, 'MODULE')])
                        nodes.append(parent)
                        # add parent as potential next caller
                        next_callers.append(parent)
                        # add other children of parent as potential next caller
                        if parent in memberships:
                            for m in memberships[parent]:
                                other_child = sep_.join([parent, m])
                                # check whether to ignore callee
                                if not (ignore and (other_child in ignore)):
                                    # add child as potential next caller
                                    next_callers.append(other_child)
                    if (parent, child) not in edges:
                        # add edge for parent-child relationship
                        base.edge(parent, caller, arrowhead='none',
                                  arrowtail='diamond')
                        edges.append((parent, child))
                else:
                    # assign caller to base graph
                    graphs[caller] = base

                # add node for caller
                graphs[caller.split(sep_)[0]].node(
                    name=caller, label=caller.split(sep_)[-1],
                    **node_attrs[kinds.get(caller, 'VARIABLE')]
                )
                nodes.append(caller)

            # collect callees of current caller (if any)
            callees = caller_callees.get(caller, [])
            for callee in callees:
                if ignore and (callee in ignore):
                    continue
                # if callee not already a node, make it one
                if callee not in nodes:
                    if callee not in kinds:
                        # i.e. it is a variable
                        if without_variables:
                            continue

                    # split up parent and child in callee if possible
                    if sep_ in callee:
                        parent, child = callee.split(sep_)
                        if parent not in nodes:
                            # create cluster graph if requested
                            if clustering:
                                graph = gv.Digraph(
                                    name='_'.join(['cluster', parent]),
                                    **graph_attrs
                                )
                            else:
                                graph = base
                            graphs[parent] = graph
                            # add node for parent
                            graph.node(parent, **node_attrs[kinds.get(parent, 'MODULE')])
                            nodes.append(parent)
                            # add parent as potential next caller
                            next_callers.append(parent)
                            # add other children of parent as potential next caller
                            if parent in memberships:
                                for m in memberships[parent]:
                                    other_child = sep_.join([parent, m])
                                    # check whether to ignore callee
                                    if not (ignore and (other_child in ignore)):
                                        # add child as potential next caller
                                        next_callers.append(other_child)
                        if (parent, child) not in edges:
                            # add edge for parent-child relationship
                            base.edge(parent, callee, arrowhead='none',
                                      arrowtail='diamond')
                            edges.append((parent, child))
                    else:
                        # assign callee to base graph
                        graphs[callee] = base

                    # add node for callee
                    graphs[callee.split(sep_)[0]].node(
                        name=callee, label=callee.split(sep_)[-1],
                        **node_attrs[kinds.get(callee, 'VARIABLE')]
                    )
                    nodes.append(callee)

                    # store callee as potential next caller
                    next_callers.append(callee)

                # add edge between caller and callee
                if (caller, callee) not in edges:
                    base.edge(caller, callee)
                    edges.append((caller, callee))
                    if caller not in ext_caller_callers:
                        ext_caller_callers[caller] = []
                    ext_caller_callers[caller].append(callee)

        # move on to next caller rank (eliminating duplicates)
        next_callers = list(set(next_callers))
        callers = next_callers

    # if clustering requested, append clusters as sub-graphs of base graph
    if clustering:
        for parent, graph in graphs.items():
            base.subgraph(graph)

    # store graph in dot and pdf
    base.render(
        sep.join([out_dir, '{}.gv'.format(root_caller)]),
        format='pdf',
        view=False
    )

    return nodes, ext_caller_callers


def generate_sources_file(root_caller, locations, nodes, sep_, out_dir):
    # generate list of files required for compilation
    list_files = []
    for node in nodes:
        if node in locations:
            if locations[node] not in list_files:
                list_files.append(locations[node])
        elif node in _intrinsic_fortran:
            pass
        else:
            # it is a variable
            node_ = sep_.join(node.split(sep_)[:-1])
            if node_ in locations:
                if locations[node_] not in list_files:
                    list_files.append(locations[node_])
            elif node_ in _intrinsic_fortran:
                pass
            else:
                raise KeyError(f"location for node '{node}' not found")

    # eliminate duplicates
    list_files = list(set(list_files))

    # store files into sub-groups
    sub_groups = {p: [] for p in _priorities}

    for file_ in list_files:
        found = False
        # find priority
        for p in _priorities:
            if f"{sep}{p}{sep}" in file_:
                if not found:
                    # deal with lower priority sharing same name as current
                    if _priorities[p] and (f"{sep}{_priorities[p]}{sep}" in file_):
                        sub_groups[_priorities[p]].append(file_)
                    else:
                        sub_groups[p].append(file_)
                    found = True

        if not found:
            raise RuntimeError(f"no priority found for {file_}")

    # create a text file listing required source files by order of priority
    with open(sep.join([out_dir, '{}.sources'.format(root_caller)]), 'w') as f:
        for p in _priorities:
            # arbitrary alphabetical sorting within same level of priority
            list_files = sorted(sub_groups[p])
            for file_ in list_files:
                f.write(f"{file_}\n")


def generate_dependencies_file(root_caller, ext_caller_callees, locations,
                               sep_, source_dir, build_dir, out_dir):
    # gather dependencies per target
    dependencies = {}

    for caller, callees in ext_caller_callees.items():
        parent = caller.split(sep_)[0]
        try:
            target = locations[parent]
        except KeyError:
            RuntimeError(f"{parent} has no location")

        requirements = []
        for callee in callees:
            child = callee.split(sep_)[0]
            if child != parent:
                try:
                    requirements.append(locations[child])
                except KeyError:
                    RuntimeError(f"{child} has no location")

        requirements = list(set(requirements))

        if requirements:
            if target not in dependencies:
                dependencies[target] = []
            dependencies[target].extend(requirements)

    # create a file containing object dependencies for makefile
    with open(sep.join([out_dir, '{}.dependencies'.format(root_caller)]), 'w') as f:
        for target, requirements in dependencies.items():
            requirements = list(set(requirements))

            requirements = ' \\\n'.join(requirements)
            f.write(
                f"{target}: \\\n{requirements}\n\n".replace(
                    '.f90', '.o').replace(source_dir, build_dir)
            )


if __name__ == '__main__':
    # terminal interface
    parser = argparse.ArgumentParser(
        description="generate call graphs from preprocessed Fortran source code"
    )

    parser.add_argument('root_callers',
                        type=str,
                        nargs='+',
                        help="name(s) of the caller(s) in the algorithm "
                             "to use as root to call graph (use double "
                             "underscore to separate module and "
                             "subroutine/function)")
    parser.add_argument('-s', '--source_dir',
                        type=str,
                        help="path to directory containing Fortran files to "
                             "consider for call graph - default to current "
                             "working directory",
                        default='.')
    parser.add_argument('-b', '--build_dir',
                        type=str,
                        help="path to directory where object files resulting "
                             "from compilation of Fortran files are (required "
                             "for writing the dependency file) - default to "
                             "source directory",
                        default=None)
    parser.add_argument('-e', '--extension',
                        type=str,
                        help="file extension for the source code (case-sensitive) "
                             "- default to f90",
                        default='f90')
    parser.add_argument('-o', '--output_dir',
                        type=str,
                        help="path to directory where to save dot and "
                             "pdf outputs of the call graphs - default "
                             "to outputs folder",
                        default='outputs')
    parser.add_argument('-i', '--ignore',
                        type=str,
                        nargs='+',
                        help="name(s) of the callee(s) in the algorithm "
                             "to ignore in the call graph (use double "
                             "underscore to separate module and "
                             "subroutine/function)")
    parser.add_argument('-c', '--cluster',
                        dest='cluster',
                        action='store_true',
                        help="visually gather entities into their "
                             "containing modules (if any)")
    parser.add_argument('-v', '--without_variables',
                        dest='without_variables',
                        action='store_true',
                        help="option to not display the variables")
    parser.set_defaults(cluster=False, without_variables=False)

    # collect parameters
    args = parser.parse_args()

    _root_callers = args.root_callers
    _source_dir = args.source_dir
    _build_dir = args.build_dir if args.build_dir else _source_dir
    _output_dir = args.output_dir
    _extension = args.extension
    _ignore = args.ignore
    _clustering = args.cluster
    _without_variables = args.without_variables

    # gather all Fortran files found in source directory and its sub-directories
    _sep = '__'
    _fortran_files = glob(
        sep.join([_source_dir, '/**/*.{}'.format(_extension)]),
        recursive=True
    )

    # parse all source code
    _caller_callees, _memberships, _kinds, _locations = parse_fortran_files(
        _fortran_files, _sep
    )

    # for each root caller
    for _root_caller in _root_callers:
        # generate a call graph
        _nodes, _ext_caller_callees = generate_dot_and_pdf(
            _root_caller, _caller_callees, _memberships, _kinds,
            _sep, _output_dir, _ignore, _clustering, _without_variables
        )

        # create sources and dependencies files
        generate_sources_file(
            _root_caller, _locations, _nodes, _sep, _output_dir
        )

        generate_dependencies_file(
            _root_caller, _ext_caller_callees, _locations, _sep,
            _source_dir, _build_dir, _output_dir
        )
