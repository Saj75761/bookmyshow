import time
from django.shortcuts import render, redirect ,get_object_or_404
from django.db import connection, IntegrityError
from django.db.models import Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.conf import settings
from .models import Movie, Theater, Seat, Booking, Genre, Language
from django.contrib.auth.decorators import login_required

def movie_list(request):
    # Check if AJAX request
    is_ajax = request.GET.get('ajax') == '1' or request.headers.get('x-requested-with') == 'XMLHttpRequest'

    # Extract filter parameters
    search_query = request.GET.get('search', '').strip()
    genre_ids = request.GET.get('genres', '')
    language_ids = request.GET.get('languages', '')
    sort_by = request.GET.get('sort', 'rating_desc')
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 12))

    # Parse IDs
    genre_id_list = [int(x) for x in genre_ids.split(',') if x.strip().isdigit()]
    language_id_list = [int(x) for x in language_ids.split(',') if x.strip().isdigit()]

    # Track DB execution stats
    start_time = time.time()
    initial_queries = len(connection.queries)

    # 1. Build Base Movie Queryset
    movies_qs = Movie.objects.all()

    # Apply Search filter
    if search_query:
        movies_qs = movies_qs.filter(name__icontains=search_query)

    # Apply Language filter (multi-select OR logic)
    if language_id_list:
        movies_qs = movies_qs.filter(language_id__in=language_id_list)

    # Apply Genre filter (multi-select OR logic)
    if genre_id_list:
        movies_qs = movies_qs.filter(genres__id__in=genre_id_list).distinct()

    # 2. Apply Sorting
    if sort_by == 'rating_desc':
        movies_qs = movies_qs.order_by('-rating')
    elif sort_by == 'year_desc':
        movies_qs = movies_qs.order_by('-release_year')
    elif sort_by == 'title_asc':
        movies_qs = movies_qs.order_by('name')
    else:
        movies_qs = movies_qs.order_by('-rating')  # Default

    # Optimize relationships fetching to prevent N+1 queries
    movies_qs = movies_qs.select_related('language').prefetch_related('genres')

    # 3. Paginate
    paginator = Paginator(movies_qs, limit)
    try:
        page_obj = paginator.page(page)
    except Exception:
        page_obj = paginator.page(1)

    # 4. Calculate Dynamic Counts (Faceted Filtering)
    # Genre counts: Applied language and search filters, but NOT genre filters.
    genre_movies = Movie.objects.all()
    if search_query:
        genre_movies = genre_movies.filter(name__icontains=search_query)
    if language_id_list:
        genre_movies = genre_movies.filter(language_id__in=language_id_list)

    # Fast aggregation on junction table:
    genre_counts_raw = Movie.genres.through.objects.filter(
        movie__in=genre_movies
    ).values('genre_id').annotate(count=Count('movie_id'))
    genre_counts_dict = {item['genre_id']: item['count'] for item in genre_counts_raw}

    # Language counts: Applied genre and search filters, but NOT language filters.
    lang_movies = Movie.objects.all()
    if search_query:
        lang_movies = lang_movies.filter(name__icontains=search_query)
    if genre_id_list:
        lang_movies = lang_movies.filter(genres__id__in=genre_id_list).distinct()

    lang_counts_raw = lang_movies.values('language_id').annotate(count=Count('id'))
    lang_counts_dict = {item['language_id']: item['count'] for item in lang_counts_raw}

    # Retrieve all Genres and Languages to return full lists with accurate counts (including 0)
    all_genres = list(Genre.objects.values('id', 'name'))
    for g in all_genres:
        g['count'] = genre_counts_dict.get(g['id'], 0)

    all_languages = list(Language.objects.values('id', 'name'))
    for l in all_languages:
        l['count'] = lang_counts_dict.get(l['id'], 0)

    # Measure DB Timing & Query Count
    db_time_ms = round((time.time() - start_time) * 1000, 2)
    query_count = len(connection.queries) - initial_queries if settings.DEBUG else 0
    
    # Extract query plans and SQL strings for debugging / stats panel
    executed_queries = []
    if settings.DEBUG:
        for q in connection.queries[initial_queries:]:
            sql = q.get('sql', '')
            explanation = "Index lookup used."
            if "movies_movie_genres" in sql:
                explanation = "Uses composite index on movies_movie_genres."
            elif "language_id" in sql:
                explanation = "Uses foreign key index on language_id."
            elif "ORDER BY" in sql or "rating" in sql or "release_year" in sql:
                explanation = "Uses sorting indexes on rating or release_year."
            executed_queries.append({
                'sql': sql,
                'time': q.get('time', 'N/A'),
                'explanation': explanation
            })

    # 5. Format JSON Response
    if is_ajax:
        movies_data = []
        for m in page_obj.object_list:
            movies_data.append({
                'id': m.id,
                'name': m.name,
                'image_url': m.image.url if m.image else '/media/movies/placeholder.jpg',
                'rating': float(m.rating),
                'cast': m.cast,
                'description': m.description,
                'release_year': m.release_year,
                'duration': m.duration,
                'language': m.language.name if m.language else 'Unknown',
                'genres': [g.name for g in m.genres.all()]
            })

        return JsonResponse({
            'movies': movies_data,
            'pagination': {
                'page': page_obj.number,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'total_movies': paginator.count
            },
            'genres': all_genres,
            'languages': all_languages,
            'stats': {
                'db_time_ms': db_time_ms,
                'query_count': query_count,
                'queries': executed_queries
            }
        })

    # Render static page shell
    return render(request, 'movies/movie_list.html', {
        'genres': all_genres,
        'languages': all_languages,
        'initial_movies_count': paginator.count
    })

def theater_list(request,movie_id):
    movie = get_object_or_404(Movie,id=movie_id)
    theater=Theater.objects.filter(movie=movie)
    return render(request,'movies/theater_list.html',{'movie':movie,'theaters':theater})



@login_required(login_url='/login/')
def book_seats(request,theater_id):
    theaters=get_object_or_404(Theater,id=theater_id)
    seats=Seat.objects.filter(theater=theaters)
    if request.method=='POST':
        selected_Seats= request.POST.getlist('seats')
        error_seats=[]
        if not selected_Seats:
            return render(request,"movies/seat_selection.html",{'theaters':theaters,"seats":seats,'error':"No seat selected"})
        for seat_id in selected_Seats:
            seat=get_object_or_404(Seat,id=seat_id,theater=theaters)
            if seat.is_booked:
                error_seats.append(seat.seat_number)
                continue
            try:
                Booking.objects.create(
                    user=request.user,
                    seat=seat,
                    movie=theaters.movie,
                    theater=theaters
                )
                seat.is_booked=True
                seat.save()
            except IntegrityError:
                error_seats.append(seat.seat_number)
        if error_seats:
            error_message=f"The following seats are already booked: {', '.join(error_seats)}"
            return render(request,'movies/seat_selection.html',{'theaters':theaters,"seats":seats,'error':error_message})
        return redirect('profile')
    return render(request,'movies/seat_selection.html',{'theaters':theaters,"seats":seats})

