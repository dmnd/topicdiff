import sys
import json
import argparse
import clean
import StringIO

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

    def topic_report(self, buffer, old=None, new=None, indent=0):
        topic_buffer = StringIO.StringIO()

        if not new and not old:
            old = self.root_old
            new = self.root_new

        if new and old:
            assert get_id(old) == get_id(new), "ids don't match: %r, %r" % (
                get_id(new), get_id(old))

        cold = old.get('children', []) if old else []
        cnew = new.get('children', []) if new else []

        cold_set = set()
        if old:
            cold_set = set(get_id(c) for c in old.get('children', []))
        cnew_set = set()
        if new:
            cnew_set = set(get_id(c) for c in new.get('children', []))

        self_changed = cold != cnew

        added = cnew_set - cold_set
        removed = cold_set - cnew_set

        added_str = "%+4i" % len(added) if added else '    '
        removed_str = "%+4i" % -len(removed) if removed else '    '

        if added and removed:
            sdchildren = "%s,%s" % (added_str, removed_str)
        else:
            sdchildren = "%s %s" % (added_str, removed_str)

        # check if order of children changed
        reordered = any(cold != cnew
                        for cold, cnew in zip(cold_set, cnew_set))

        # check if the topic has become curated
        def has_separator(children):
            return any(c[0] == 'Separator' for c in children)
        curated = has_separator(cnew_set)

        colour = None
        if curated:
            colour = colours['blue']
        elif reordered:
            colour = colours['yellow']

        tags = set()
        if reordered:
            tags.add('reordered')
        if curated:
            tags.add('curated')

        id = get_id(old) if old else get_id(new)
        pindent("%(dchildren)s %(id)s (%(oc)i -> %(nc)i) %(tags)s" % {
            'dchildren': sdchildren,
            'id': id[1],
            'oc': len(cold_set),
            'nc': len(cnew_set),
            'tags': ", ".join(tags)}, indent, colour, buffer=topic_buffer)

        def recurse(children, other_children, other_index, root, fn, done):
            """For each child in children, recurse for all that are topics.
            Contains logic to find the location of the corresponding new child
            in the new tree.

            Note that this will NOT recurse for any items not inside the
            children list. For that, run again with children and other_children
            swapped.
            """
            changed = False
            for child in children:
                if child['kind'] == "Topic":
                    id = get_id(child)
                    if id in children_done:
                        continue
                    children_done.add(id)

                    # find the new location
                    other_child = None
                    if id in other_index:
                        other_child_path = other_index[id]
                        other_child = other_child_path[0].get(root)

                    children_done.add(id)
                    child_changed = fn(child, other_child)
                    changed = changed or child_changed
            return changed

        children_done = set()
        # recurse for all old children that were deleted or changed
        children_changed = recurse(cold, cnew, self.index_new, self.root_new,
            lambda c, oc: self.topic_report(topic_buffer, c, oc, indent + 4),
            children_done)

        # if there are still new ids after subtracting the done ones, print
        # a separator
        new_ids = {get_id(c) for c in cnew if c['kind'] == 'Topic'}
        if (new_ids - children_done):
            children_changed = True
            pindent('.' * 9, indent + 4, buffer=topic_buffer)

            # now recurse for all children that are brand new in the new tree
            recurse(cnew, cold, self.root_old, self.root_old,
                lambda c, oc: self.topic_report(
                    topic_buffer, oc, c, indent + 4),
                children_done)

        if self_changed or children_changed or args.no_collapse:
            buffer.write(topic_buffer.getvalue())
            return True
        else:
            return False

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
        return ("Separator", "Separator")
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
    parts = []

    def __init__(self, parts):
        self.parts = parts

    def __repr__(self):
        return ("/" + "/".join(p[1] for p in self.parts[1:-1]) +
                "/" + Path.str_key(self.parts[-1]))

    def get(self, root):
        assert get_id(root) == self.parts[0]

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
    parser.add_argument('--kinds', nargs='*', default=['Exercise'])
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
