
minimal_fields = {
    "Topic": [
        "kind",
        "id",
        "children"
    ],

    "Video": [
        "kind",
        "readable_id"
    ],

    "Exercise": [
        "kind",
        "name"
    ],

    "Url": [
        "kind",
        "id"
    ],

    "CustomStack": [
        "kind",
        "id"
    ],

    "Separator": [
        "kind"
    ],
}

# topic_new_fields = (
#     'title',
#     'standalone_title',
#     'description',
#     'tags')

# video_new_fields = (
#     "youtube_id",
#     "title",
#     "url",
#     "description",
#     "keywords",
#     "duration",
#     "readable_id",
#     "views")
# exercise_new_fields = (
#     "related_video_keys")


def strip_extraneous_fields(node):
    """modifies the dict in place"""
    kind = node["kind"]
    if kind in minimal_fields:
        allowed = minimal_fields[kind]
        for key in node.keys():
            if key not in allowed:
                del node[key]

    for child in node.get("children", []):
        strip_extraneous_fields(child)

import sys
import json


def main():
    file_name = sys.argv[1]
    with open(file_name) as f:
        data = json.loads(f.read())
    strip_extraneous_fields(data)
    print json.dumps(data, sort_keys=True, indent=2)

if __name__ == "__main__":
    main()
