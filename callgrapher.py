from glob import glob
from os import sep
import re
import csv
import graphviz as gv
import argparse


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
                                    # add if callee is itself a caller
                                    if other_child in caller_callees:
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
                                        # add if callee is itself a caller
                                        if other_child in caller_callees:
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

                # add edge between caller and callee
                if (caller, callee) not in edges:
                    base.edge(caller, callee)
                    edges.append((caller, callee))
                # store callee as potential next caller
                next_callers.append(callee)
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
        view=True
    )

    return nodes


def generate_loc(root_caller, locations, nodes, out_dir):
    # create a simple text files to know where to find callees
    with open(sep.join([out_dir, '{}.txt'.format(root_caller)]), 'w') as f:
        w = csv.writer(f, delimiter='\t')
        keys = sorted(list(locations.keys()))
        for key in keys:
            if key in nodes:
                w.writerow([key, locations[key]])


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
                        help="path to top-level directory containing "
                             "Fortran files to consider for call graph "
                             "- default to current working directory",
                        default='.')
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

    root_callers = args.root_callers
    source_dir = args.source_dir
    output_dir = args.output_dir
    extension = args.extension
    _ignore = args.ignore
    _clustering = args.cluster
    _without_variables = args.without_variables

    # gather all Fortran files found in source directory and its sub-directories
    _sep = '__'
    _fortran_files = glob(sep.join([source_dir, '/**/*.{}'.format(extension)]),
                          recursive=True)

    # parse all source code
    _caller_callees, _memberships, _kinds, _locations = parse_fortran_files(
        _fortran_files, _sep
    )

    # for each root caller
    for _root_caller in root_callers:
        # generate a call graph
        _nodes = generate_dot_and_pdf(
            _root_caller, _caller_callees, _memberships, _kinds,
            _sep, output_dir, _ignore, _clustering, _without_variables
        )

        # generate a location helper
        generate_loc(_root_caller, _locations, _nodes, output_dir)
