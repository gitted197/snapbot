"""Selectors for both observed Snapchat recipient-picker layouts."""
SEARCH_IDS = ("scu_search_text_field", "com.snapchat.android:id/input_field_edit_text")
SEND_IDS = ("send_button", "com.snapchat.android:id/send_to_send_button")
PANEL_IDS = ("send_confirmation_view", "com.snapchat.android:id/send_to_confirmation_bar")


def by_ids(tree, ids):
    return next((n for n in tree.iter("node") if n.get("resource-id") in ids), None)


def picker_visible(tree):
    return by_ids(tree, SEARCH_IDS) is not None


def recipient_matches(tree, username):
    parents = {child: parent for parent in tree.iter() for child in parent}
    matches = []
    for node in tree.iter("node"):
        if node.get("text") != username or node.get("package") != "com.snapchat.android":
            continue
        if node.get("class") == "android.widget.EditText":
            continue
        ancestor = node
        in_panel = False
        in_list = False
        while ancestor is not None:
            if ancestor.get("resource-id") in PANEL_IDS:
                in_panel = True
            if ancestor.get("class") == "androidx.recyclerview.widget.RecyclerView" or ancestor.get("resource-id") == "recipient_picker.collection_view":
                in_list = True
            ancestor = parents.get(ancestor)
        if not in_panel and (node.get("resource-id") == "result-title" or
                             (in_list and node.get("class") == "javaClass" and not node.get("resource-id"))):
            matches.append(node)
    return matches


def unique_recipient(tree, username):
    matches = recipient_matches(tree, username)
    if len(matches) > 1:
        raise RuntimeError(f"Meerdere ontvangers met exact de naam {username!r}; selectie gestopt")
    return matches[0] if matches else None


def selection_visible(tree, username):
    # Recipient labels inside the confirmation bar are authoritative. Do not
    # confuse the list name or search field contents with a selected recipient.
    panel = by_ids(tree, PANEL_IDS)
    if panel is None:
        return False
    labels = [n.get("text", "") for n in panel.iter("node")
              if n.get("class") in ("android.widget.TextView", "javaClass") and n.get("text")]
    return labels == [username]
