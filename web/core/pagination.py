from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


PAGE_SIZE = 5


def paginate_queryset(queryset, request, page_param="page", per_page=PAGE_SIZE):
    """Paginate a Django queryset on the server. Defaults to 5 records/page."""
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(page_param, 1)
    try:
        return paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        return paginator.page(1)
