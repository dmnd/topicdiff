import sys
import json
import argparse
import clean
import StringIO
import difflib

ids = {
    "Topic": "id",
    "Exercise": "name",
    "Video": "readable_id",
    "CustomStack": "id",
    "Separator": "kind",
    "Url": "id"
}

colours = {
    'red': 31,
    'green': 32,
    'yellow': 33,
    'blue': 34,
}


def find_element(tree, predicate):
    """Find the first element in the tree that matches a predicate"""
    if predicate(tree):
        return tree
    for child in tree.get('children', []):
        result = find_element(child, predicate)
        if result:
            return result
    return None


class DiffContext(object):
    root_old = None
    root_new = None
    index_old = None
    index_new = None

    def __init__(self, old_file, new_file, root=None):
        self.root_old = self._read_file(old_file, root)
        self.root_new = self._read_file(new_file, root)

        # build indices
        self.index_old = index_topic(self.root_old)
        self.index_new = index_topic(self.root_new)

    def _read_file(self, file_name, root=None):
        """Read a JSON file and return only the element that matches the
        desired root"""
        with open(file_name) as f:
            data = json.loads(f.read())

        if root:
            data = find_element(data, lambda el: get_id(el)[1] == root)
            if not data:
                raise Exception("Can't find node with id %s" % root)

        clean.strip_extraneous_fields(data)

        return data

    def topic_report(self, buffer, old=None, new=None, indent=0, moved=False):
        # if nothing supplied, assume comparing 2 root elements
        if not new and not old:
            old = self.index_old[get_id(self.root_old)][0]
            new = self.index_new[get_id(self.root_new)][0]

        self_changed = old is None or new is None

        self_added = False
        self_removed = False
        self_moved = False
        if old is None:
            self_added = True
        elif new is None:
            self_removed = True
        elif new and old:
            assert old.id() == new.id(), "ids don't match: %r, %r" % (
                new.id(), old.id())

        cold = old.get(self.root_old).get('children', []) if old else []
        cnew = new.get(self.root_new).get('children', []) if new else []

        cold_set = set(get_id(c) for c in cold)
        cnew_set = set(get_id(c) for c in cnew)

        added = cnew_set - cold_set
        removed = cold_set - cnew_set

        added_str = "%+4i" % len(added) if added else '    '
        removed_str = "%+4i" % -len(removed) if removed else '    '

        if added and removed:
            sdchildren = "%s,%s" % (added_str, removed_str)
        else:
            sdchildren = "%s %s" % (added_str, removed_str)

        # check if the topic has become curated
        def has_separator(children):
            return any(c[0] == 'Separator' for c in children)
        curated = has_separator(cnew_set) and not has_separator(cold_set)

        tags = set()
        colour = None
        if moved:
            if self_added:
                colour = colours['yellow']
            else:
                colour = colours['red']
                tags.add('repos')
        elif self_added:
            colour = colours['green']
        elif self_removed:
            colour = colours['red']
        elif curated:
            colour = colours['blue']
            tags.add('newly curated')

        id = old.id() if old else new.id()
        if cold_set or cnew_set:
            children_count = "(%(oc)i -> %(nc)i) " % {
                'oc': len(cold_set),
                'nc': len(cnew_set),
            }
        else:
            children_count = ""

        # buffer to write to so we can throw away output later
        topic_buffer = StringIO.StringIO()

        pindent("%(dchildren)s %(id)s %(children_count)s %(tags)s" % {
            'dchildren': sdchildren,
            'id': Path.str_key(id),
            'children_count': children_count,
            'tags': ", ".join(tags)}, indent, colour, buffer=topic_buffer)

        def make_path(parent_path, id):
            path = parent_path.copy()
            path.parts.append(id)
            return path

        def recurse(path, children, other_children, fn):
            changed = False
            sm = difflib.SequenceMatcher(
                a=[get_id(c) for c in children],
                b=[get_id(c) for c in other_children])
            for op, al, ah, bl, bh in sm.get_opcodes():
                if op == 'equal':
                    for ai, bi in zip(xrange(al, ah), xrange(bl, bh)):
                        child_a = sm.a[ai]
                        child_b = sm.b[bi]
                        child_changed = fn(make_path(path, child_a),
                                           make_path(path, child_b))
                        changed = changed or child_changed
                else:  # op is replace, insert or delete
                    # handle deletions
                    for ai in xrange(al, ah):
                        child_a = sm.a[ai]

                        # the child was moved somewhere else in the topic
                        moved = child_a in sm.b
                        child_changed = fn(make_path(path, child_a), None,
                            moved=moved)
                        changed = changed or child_changed

                    # now handle insertions
                    for bi in xrange(bl, bh):
                        child_b = sm.b[bi]

                        # check to see if the child came from somewhere else in
                        # the topic.
                        moved = child_b in sm.a
                        child_changed = fn(None, make_path(path, child_b),
                            moved=moved)
                        changed = changed or child_changed
            return changed

        # recurse for all children
        children_changed = recurse(old or new, cold, cnew,
            lambda c, oc, moved=False: self.topic_report(
                topic_buffer, c, oc, indent + 4, moved=moved))

        # if args.no_collapse or self_changed or children_changed:
        buffer.write(topic_buffer.getvalue())
        return self_changed or children_changed

    def entity_report(self, kind="Exercise"):
        print
        print "%s REPORT" % kind.upper()

        old_set = {k for k in self.index_old.keys() if k[0] == kind}
        new_set = {k for k in self.index_new.keys() if k[0] == kind}

        def print_hist(hist):
            for k, v in hist.iteritems():
                print "%i: %i" % (k, v)
        print "old histogram"
        print_hist(hist({k: v for k, v in self.index_old.iteritems()
                         if k[0] == kind}))
        print "new histogram"
        print_hist(hist({k: v for k, v in self.index_new.iteritems()
                         if k[0] == kind}))
        print

        removed = old_set - new_set
        added = new_set - old_set
        possibly_changed = old_set & new_set

        print "removed: %i" % len(removed)
        removed_paths = sorted([self.index_old[k] for k in removed])
        for p in removed_paths:
            pindent(p, colour=colours['red'], indent=False)
        if removed:
            print

        print "added: %i" % len(added)
        added_paths = sorted([self.index_new[k] for k in added])
        for p in added_paths:
            pindent(p, colour=colours['green'], indent=False)
        if added:
            print

        changed = set()
        unchanged = set()
        for key in possibly_changed:
            path = self.index_old[key]
            new_path = self.index_new[key]
            if path != new_path:
                changed.add(key)
            else:
                unchanged.add(key)
        print "unchanged: %i" % len(unchanged)

        changed_paths = [(self.index_old[k], self.index_new[k])
                         for k in changed]
        copied = []
        other = []
        for p in changed_paths:
            if p[0][0] in p[1]:
                copied.append(p)
            else:
                other.append(p)

        if copied:
            print
        print "copied: %i" % len(copied)
        for old_path, new_path in sorted(copied):
            dests = [p for p in new_path if p not in old_path]
            pindent(old_path, indent=False)
            pindent(dests, colour=colours['green'], indent=False)
        if copied:
            print

        print "other: %i" % len(other)
        for old_path, new_path in sorted(other):
            pindent(old_path, colour=colours['red'], indent=False)
            pindent(new_path, colour=colours['green'], indent=False)
        if other:
            print


def pindent(s="", n=0, colour=None, indent=True, buffer=None):
    if buffer is None:
        buffer = sys.stdout

    global args
    if indent and not args.no_indent:
        buffer.write((n * ' ') + '.')
    if s:
        if colour and not args.no_colour:
            buffer.write('\033[%im%s\033[0m\n' % (colour, s))
        else:
            buffer.write("%s\n" % s)


def get_id(entity):
    if entity["kind"] == "Separator":
        return ("Separator", "_separator")
    else:
        return (entity["kind"], entity[ids[entity['kind']]])


def hist(dict):
    hist = {}
    for k, v in dict.iteritems():
        n = len(v)
        hist[n] = hist.get(n, 0) + 1
    return hist


class CommonEqualityMixin(object):
    def __eq__(self, other):
        return (isinstance(other, self.__class__)
            and self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not self.__eq__(other)


class Path(CommonEqualityMixin):
    def __init__(self, parts):
        self.parts = parts

    def __repr__(self):
        # don't show root
        path = [Path.str_key(p) for p in self.parts[:-1]]
        if path:
            path[0] = ""
        path.append(Path.str_key(self.id()))
        return "/".join(path)

    def __hash__(self):
        return reduce(lambda s, p: s ^ hash(p), self.parts, 0)

    def get(self, root):
        assert get_id(root) == self.root()

        for key in self.parts[1:]:
            next = None
            for child in root.get('children', []):
                if get_id(child) == key:
                    next = child
                    break
            if not next:
                raise Exception("Cannot find %r" % (key,))
            root = next
        return root

    def copy(self):
        return Path(list(self.parts))

    @staticmethod
    def str_key(key):
        if key[0] == "Topic":
            return key[1]
        else:
            return key[0][0].lower() + '/' + key[1]

    def id(self):
        return self.parts[-1]

    def root(self):
        return self.parts[0]


def index_topic(topic, path=None, index=None):
    index = index or {}
    path = path or []

    key = get_id(topic)
    path.append(key)
    index.setdefault(key, []).append(Path(list(path)))

    for child in topic.get('children', []):
        index_topic(child, path, index)

    path.pop()
    return index


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-colour', action='store_true', default=False,
                      help='Use colours in output')
    parser.add_argument('--no-indent', action='store_true', default=False,
                      help='Indent output')
    parser.add_argument('--no-collapse', action='store_true', default=False,
                      help='Only show nodes that have changed')
    parser.add_argument('--kinds', nargs='*', default=['Topic'])
    parser.add_argument('--root', default='root', help='Restrict report to '
        'element with this id')
    parser.add_argument('old', help='old topictree.json')
    parser.add_argument('new', help='new topictree.json')
    parser.add_argument('command', help='what type of report to run. '
        'diff or entity')
    return parser.parse_args()


def main(args):
    old_file, new_file = sys.argv[1:3]
    context = DiffContext(old_file, new_file, args.root)
    if args.command == 'diff':
        buffer = StringIO.StringIO()
        context.topic_report(buffer=buffer)
        sys.stdout.write(buffer.getvalue())
    elif args.command == 'entity':
        for entity in args.kinds:
            context.entity_report(kind=entity)


if __name__ == '__main__':
    global args
    args = parse_args()
    main(args)
