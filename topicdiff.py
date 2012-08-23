import sys
import json

ids = {
    "Topic": "id",
    "Exercise": "name",
    "Video": "readable_id",
    "CustomStack": "id",
    "Separator": "kind",
    "Url": "id"
}


class DiffContext(object):
    root_old = None
    root_new = None
    index_old = None
    index_new = None

    def __init__(self, old_file, new_file):
        with open(old_file) as f:
            self.root_old = json.loads(f.read())

        with open(new_file) as f:
            self.root_new = json.loads(f.read())

        # build indices
        self.index_old = index_topic(self.root_old)
        self.index_new = index_topic(self.root_new)

    def topic_report(self, old, new, indent=0):
        if new and old:
            assert get_id(old) == get_id(new), "ids don't match: %r, %r" % (
                get_id(new), get_id(old))


        children_old = old.get('children', []) if old else []
        children_new = new.get('children', []) if new else []

        # check if number of children changed
        nchildren = len(children_new) if new else -1
        ochildren = len(children_old) if old else -1
        dchildren = nchildren - ochildren
        if new and old:
            sdchildren = ("%+4i" % dchildren) if dchildren else '    '
        elif old:
            sdchildren = '   d'
        else:
            sdchildren = '   a'

        # check if order of children changed
        reordered = any(get_id(cold) != get_id(cnew)
                        for cold, cnew in zip(children_old, children_new))

        # check if the topic has become curated
        def has_separator(children):
            return any(c['kind'] == 'Separator' for c in children)
        curated = has_separator(children_new)

        colours = {
            'red': 31,
            'green': 32,
            'yellow': 33,
            'blue': 34,
        }

        colour = None
        if curated:
            colour = colours['blue']
        elif sdchildren == '   d':
            colour = colours['red']
        elif sdchildren == '   a':
            color = colours['green']
        elif dchildren < 0:
            colour = colours['red']
        elif dchildren > 0:
            colour = colours['green']
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
            'oc': ochildren,
            'nc': nchildren,
            'tags': ", ".join(tags)}, indent, colour)

        def recurse(children, other_children, other_index, root, fn, done):
            """For each child in children, recurse for all that are topics.
            Contains logic to find the location of the corresponding new child
            in the new tree.

            Note that this will NOT recurse for any items not inside the
            children list. For that, run again with children and other_children
            swapped.
            """
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
                        other_child = get_from_path(
                            other_child_path, root)

                    children_done.add(id)
                    fn(child, other_child)

        children_done = set()
        # recurse for all old children that were delete or changed
        recurse(children_old, children_new, self.index_new, self.root_new,
            lambda c, oc: self.topic_report(c, oc, indent + 4), children_done)

        # if there are still new ids after subtracting the done ones, print
        # a separator
        new_ids = {get_id(c) for c in children_new if c['kind'] == 'Topic'}
        if (new_ids - children_done):
            pindent('.' * 9, indent + 4)

        # now recurse for all children that are brand new in the new tree
        recurse(children_new, children_old, self.root_old, self.root_old,
            lambda c, oc: self.topic_report(oc, c, indent + 4), children_done)


colour_enabled = True
indentation_enabled = True


def pindent(s="", n=0, colour=None):
    if indentation_enabled:
        sys.stdout.write((n * ' ') + '.')
    if s:
        if colour_enabled and colour:
            print '\033[%im%s\033[0m' % (colour, s)
        else:
            print s


def get_id(entity):
    if entity["kind"] == "Separator":
        return ("Separator", "Separator")
    else:
        return (entity["kind"], entity[ids[entity['kind']]])


def get_from_path(path, root):
    assert get_id(root) == path[0]
    path.pop(0)

    while path:
        key = path.pop(0)
        next = None
        for child in root.get('children', []):
            if get_id(child) == key:
                next = child
                break
        if not next:
            raise Exception("Cannot find %r" % (key,))
        root = next
    return root


def index_topic(topic, path=None, index=None):
    index = index or {}
    path = path or []

    key = get_id(topic)
    path.append(key)
    index[key] = [p for p in path]

    for child in topic.get('children', []):
        index_topic(child, path, index)

    path.pop()
    return index


def main():
    old_file, new_file = sys.argv[1:3]
    context = DiffContext(old_file, new_file)
    context.topic_report(context.root_old, context.root_new)

if __name__ == "__main__":
    main()
