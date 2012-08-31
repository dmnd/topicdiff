
import sys
import json

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

new_fields = {
    'Topic': [
        'title',
        'standalone_title',
        'description',
        'tags'
    ],
    'Video': [
        "date_added",
        "description",
        "duration",
        "extra_properties",
        "has_questions",
        "keywords",
        "title",
        "views",
        "youtube_id"
    ],
    'Exercise': [
        "author_name",
        "covers",
        "creation_date",
        "description",
        "display_name",
        "file_name",
        "h_position",
        "kind",
        "live",
        "name",
        "prerequisites",
        "pretty_display_name",
        "related_video_readable_ids",
        "seconds_per_fast_problem",
        "sha1",
        "short_display_name",
        "summative",
        "tags",
        "v_position"
    ]
}


def strip_extraneous_fields(node, use_new_fields=False):
    """modifies the dict in place"""
    kind = node["kind"]
    if kind in minimal_fields:
        allowed = minimal_fields[kind]
        if use_new_fields:
            allowed += new_fields.get(kind, [])
        for key in node.keys():
            if key not in allowed:
                del node[key]

    for child in node.get("children", []):
        strip_extraneous_fields(child)


def main():
    file_name = sys.argv[1]
    with open(file_name) as f:
        data = json.loads(f.read())
    strip_extraneous_fields(data)
    print json.dumps(data, sort_keys=True, indent=2)

if __name__ == "__main__":
    main()
