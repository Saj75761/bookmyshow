import os
import random
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from PIL import Image, ImageDraw
from movies.models import Language, Genre, Movie



class Command(BaseCommand):
    help = "Seeds the database with 5000+ movies, 10 languages, and 12 genres."

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding...")

        # 1. Create a beautiful placeholder poster image
        self.stdout.write("Generating placeholder poster image...")
        media_dir = os.path.join(settings.MEDIA_ROOT, "movies")
        os.makedirs(media_dir, exist_ok=True)
        img_path = os.path.join(media_dir, "placeholder.jpg")

        # Generate deep indigo image
        img = Image.new("RGB", (300, 450), color="#1e1b4b")  # Dark Indigo
        draw = ImageDraw.Draw(img)
        # Draw indigo borders
        draw.rectangle([15, 15, 285, 435], outline="#6366f1", width=4)
        # Draw film strip representation
        for y in range(30, 420, 40):
            draw.rectangle([25, y, 40, y + 20], fill="#312e81")
            draw.rectangle([260, y, 275, y + 20], fill="#312e81")
        # Save image
        img.save(img_path)
        relative_img_path = "movies/placeholder.jpg"

        # 2. Seed Languages
        self.stdout.write("Seeding languages...")
        languages_list = [
            "English", "Spanish", "French", "German", "Japanese",
            "Korean", "Hindi", "Telugu", "Tamil", "Malayalam"
        ]
        languages = []
        for name in languages_list:
            lang, _ = Language.objects.get_or_create(name=name)
            languages.append(lang)

        # 3. Seed Genres
        self.stdout.write("Seeding genres...")
        genres_list = [
            "Action", "Comedy", "Drama", "Sci-Fi", "Romance",
            "Thriller", "Horror", "Animation", "Mystery", "Fantasy",
            "Adventure", "Biography"
        ]
        genres = []
        for name in genres_list:
            genre, _ = Genre.objects.get_or_create(name=name)
            genres.append(genre)

        # 4. Clear old movies (leaving user created ones or clearing all for demonstration)
        self.stdout.write("Clearing existing movie records (seeded ones)...")
        Movie.objects.filter(image=relative_img_path).delete()

        # 5. Generate 5,000 movies
        self.stdout.write("Generating 5000+ movie records...")
        
        adjectives = [
            "The Dark", "Silent", "Lost", "Golden", "Eternal", "Broken", "Hidden", "Secret",
            "Fallen", "Last", "First", "Future", "Midnight", "Ancient", "Cosmic", "Wild",
            "Deadly", "Crimson", "Shadowy", "Burning", "Infinite", "Stellar", "Iron", "Frozen"
        ]
        nouns = [
            "Knight", "Whisper", "Journey", "Empire", "Legacy", "Horizon", "Heart", "Dream",
            "Shadow", "Kingdom", "Warrior", "Rebel", "Storm", "Thunder", "Ocean", "Star",
            "Planet", "City", "Castle", "Forest", "Ghost", "Chronicle", "Destiny", "Voyage"
        ]
        suffixes = [
            "Part II", "Rising", "Reborn", "Legacy", "Returns", "Apocalypse", "Chronicles",
            "Origin", "Beyond", "Forever", "Saga", "Dawn", "Reckoning", "Game"
        ]
        casts = [
            "Leonardo DiCaprio, Cillian Murphy, Elliot Page",
            "Christian Bale, Heath Ledger, Aaron Eckhart",
            "Robert Downey Jr., Chris Evans, Scarlett Johansson",
            "Matthew McConaughey, Anne Hathaway, Jessica Chastain",
            "Brad Pitt, Edward Norton, Helena Bonham Carter",
            "Tom Hanks, Robin Wright, Gary Sinise",
            "Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss",
            "Morgan Freeman, Tim Robbins, Bob Gunton",
            "Al Pacino, Marlon Brando, James Caan",
            "Joaquin Phoenix, Robert De Niro, Zazie Beetz"
        ]

        movies_to_create = []
        created_titles = set()
        
        for i in range(5100):
            # Generate a unique title
            title = ""
            while not title or title in created_titles:
                choice_type = random.choice([1, 2, 3])
                if choice_type == 1:
                    title = f"{random.choice(adjectives)} {random.choice(nouns)}"
                elif choice_type == 2:
                    title = f"The {random.choice(nouns)} of {random.choice(nouns)}"
                else:
                    title = f"{random.choice(adjectives)} {random.choice(nouns)}: {random.choice(suffixes)}"
                if len(created_titles) > 1000 and random.random() < 0.2:
                    title += f" {random.randint(2, 9)}"

            created_titles.add(title)
            
            rating = round(random.uniform(5.0, 9.8), 1)
            release_year = random.randint(1990, 2026)
            duration = random.randint(80, 185)
            language = random.choice(languages)
            cast = random.choice(casts)
            description = f"An epic {random.choice(genres_list).lower()} movie about a {title.lower()} that changes everything."

            movies_to_create.append(
                Movie(
                    name=title,
                    image=relative_img_path,
                    rating=rating,
                    cast=cast,
                    description=description,
                    language=language,
                    release_year=release_year,
                    duration=duration
                )
            )

        # Bulk create movies
        self.stdout.write("Saving movies to database...")
        with transaction.atomic():
            created_movies = Movie.objects.bulk_create(movies_to_create, batch_size=1000)

        # 6. Seed Movie-Genre many-to-many links in bulk
        self.stdout.write("Linking movies to genres in bulk...")
        MovieGenreLink = Movie.genres.through
        links = []
        
        for movie in created_movies:
            # Assign 1 to 3 random genres
            assigned_genres = random.sample(genres, k=random.randint(1, 3))
            for genre in assigned_genres:
                links.append(
                    MovieGenreLink(movie_id=movie.id, genre_id=genre.id)
                )

        # Bulk create M2M relations
        with transaction.atomic():
            MovieGenreLink.objects.bulk_create(links, batch_size=2000)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {len(created_movies)} movies, "
                f"{len(languages)} languages, and {len(genres)} genres!"
            )
        )
