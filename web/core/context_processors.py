"""Context available to every template."""


def active_menu(request):
    """Tell the sidebar which page is being shown.

    The sidebar highlights itself by comparing `current` against a URL name.
    Views used to set that by hand, which meant 14 of the project's 71
    render() calls got it right, four of those disagreed with the sidebar
    about hyphens versus underscores, and every other page rendered with no
    highlight at all.

    Deriving it from the resolved URL means a view cannot forget it, and a
    renamed route cannot leave a stale string behind in a view somewhere.

    `current_namespace` disambiguates names that appear in more than one
    app -- "dashboard" is both the site dashboard and the reports index.
    """
    match = getattr(request, "resolver_match", None)

    if match is None:
        # No URL has been resolved yet: a 404 or an error view.
        return {"current": "", "current_namespace": ""}

    return {
        "current": match.url_name or "",
        "current_namespace": match.namespace or "",
    }
