import re
import datetime
from urllib.parse import urlparse
from app.database import get_db
from app.services.tags import set_post_tags, get_tags_for_post
from app.services.youtube import extract_youtube_id

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text or "post"

def validate_download_url(url: str) -> bool:
    if not url:
        return True
    url = url.strip()
    try:
        result = urlparse(url)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False

def dict_from_row(row):
    if not row:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, (datetime.datetime, datetime.date)):
            d[k] = str(v)
    return d

def get_posts(
    page: int = 1,
    per_page: int = 10,
    section_id: int = None,
    section_slug: str = None,
    tag_slug: str = None,
    search_query: str = None,
    only_published: bool = True,
    is_featured: bool = None
):
    offset = (page - 1) * per_page
    where_clauses = []
    params = []

    if only_published:
        where_clauses.append("p.is_published = 1 AND p.published_at <= CURRENT_TIMESTAMP")

    if is_featured is not None:
        where_clauses.append("p.is_featured = %s")
        params.append(1 if is_featured else 0)

    if section_id:
        where_clauses.append("p.section_id = %s")
        params.append(section_id)
    elif section_slug:
        where_clauses.append("s.slug = %s")
        params.append(section_slug)

    if tag_slug:
        where_clauses.append("""
            p.id IN (
                SELECT pt.post_id FROM post_tags pt
                JOIN tags t ON pt.tag_id = t.id
                WHERE t.slug = %s
            )
        """)
        params.append(tag_slug.strip().lower())

    if search_query:
        search_term = f"%{search_query.strip()}%"
        where_clauses.append("""
            (
                p.title ILIKE %s OR 
                p.content ILIKE %s OR 
                p.summary ILIKE %s OR
                s.name ILIKE %s OR
                p.id IN (
                    SELECT pt2.post_id FROM post_tags pt2
                    JOIN tags t2 ON pt2.tag_id = t2.id
                    WHERE t2.name ILIKE %s OR t2.slug ILIKE %s
                )
            )
        """)
        params.extend([search_term, search_term, search_term, search_term, search_term, search_term])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with get_db() as conn:
        cursor = conn.cursor()

        # Count total
        count_sql = f"""
            SELECT COUNT(DISTINCT p.id)
            FROM posts p
            LEFT JOIN sections s ON p.section_id = s.id
            {where_sql};
        """
        cursor.execute(count_sql, tuple(params))
        row = cursor.fetchone()
        total_count = row[0] if row else 0

        # Select rows
        query_sql = f"""
            SELECT p.*, s.name AS section_name, s.slug AS section_slug, s.icon AS section_icon
            FROM posts p
            LEFT JOIN sections s ON p.section_id = s.id
            {where_sql}
            ORDER BY p.is_featured DESC, p.published_at DESC, p.id DESC
            LIMIT %s OFFSET %s;
        """
        cursor.execute(query_sql, tuple(params + [per_page, offset]))
        rows = [dict_from_row(r) for r in cursor.fetchall()]

        # Attach tags to each post
        for post in rows:
            post["tags"] = get_tags_for_post(post["id"])

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        return {
            "posts": rows,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }

def get_post_by_slug(slug: str, only_published: bool = True):
    with get_db() as conn:
        cursor = conn.cursor()
        pub_cond = "AND p.is_published = 1 AND p.published_at <= CURRENT_TIMESTAMP" if only_published else ""
        cursor.execute(f"""
            SELECT p.*, s.name AS section_name, s.slug AS section_slug, s.icon AS section_icon
            FROM posts p
            LEFT JOIN sections s ON p.section_id = s.id
            WHERE p.slug = %s {pub_cond};
        """, (slug.strip(),))
        row = cursor.fetchone()
        if not row:
            return None
        post = dict_from_row(row)
        post["tags"] = get_tags_for_post(post["id"])
        return post

def get_post_by_id(post_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.name AS section_name, s.slug AS section_slug, s.icon AS section_icon
            FROM posts p
            LEFT JOIN sections s ON p.section_id = s.id
            WHERE p.id = %s;
        """, (post_id,))
        row = cursor.fetchone()
        if not row:
            return None
        post = dict_from_row(row)
        post["tags"] = get_tags_for_post(post["id"])
        return post

def get_popular_posts(limit: int = 5):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.name AS section_name, s.slug AS section_slug
            FROM posts p
            LEFT JOIN sections s ON p.section_id = s.id
            WHERE p.is_published = 1 AND p.published_at <= CURRENT_TIMESTAMP
            ORDER BY p.view_count DESC, p.published_at DESC
            LIMIT %s;
        """, (limit,))
        return [dict_from_row(r) for r in cursor.fetchall()]

def get_related_posts(post_id: int, section_id: int, limit: int = 4):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.name AS section_name, s.slug AS section_slug
            FROM posts p
            LEFT JOIN sections s ON p.section_id = s.id
            WHERE p.id != %s AND p.is_published = 1 AND (p.section_id = %s OR p.section_id IS NOT NULL)
            ORDER BY (p.section_id = %s) DESC, p.published_at DESC
            LIMIT %s;
        """, (post_id, section_id, section_id, limit))
        return [dict_from_row(r) for r in cursor.fetchall()]

def create_post(data: dict) -> tuple[int, str]:
    title = data.get("title", "").strip()
    if not title:
        return None, "Title is required."

    raw_slug = data.get("slug", "").strip()
    slug = slugify(raw_slug if raw_slug else title)

    download_url = (data.get("download_url") or "").strip()
    if download_url and not validate_download_url(download_url):
        return None, "Invalid Download URL. Only http:// and https:// URLs are allowed."

    yt_id = extract_youtube_id(data.get("youtube_video_id", ""))

    with get_db() as conn:
        cursor = conn.cursor()

        # Ensure slug uniqueness
        cursor.execute("SELECT id FROM posts WHERE slug = %s;", (slug,))
        if cursor.fetchone():
            count = 1
            orig = slug
            while True:
                slug = f"{orig}-{count}"
                cursor.execute("SELECT id FROM posts WHERE slug = %s;", (slug,))
                if not cursor.fetchone():
                    break
                count += 1

        cursor.execute("""
            INSERT INTO posts (
                title, slug, summary, content, thumbnail_url,
                youtube_video_id, download_url, download_label,
                section_id, is_published, is_featured,
                seo_title, seo_description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            title,
            slug,
            data.get("summary", "").strip(),
            data.get("content", "").strip(),
            data.get("thumbnail_url", "").strip(),
            yt_id,
            download_url,
            data.get("download_label", "DOWNLOAD FILE").strip() or "DOWNLOAD FILE",
            int(data["section_id"]) if data.get("section_id") else None,
            1 if data.get("is_published") else 0,
            1 if data.get("is_featured") else 0,
            data.get("seo_title", "").strip(),
            data.get("seo_description", "").strip()
        ))
        res = cursor.fetchone()
        post_id = res["id"] if isinstance(res, dict) or hasattr(res, "__getitem__") else res[0]

    tags_input = data.get("tags", "")
    set_post_tags(post_id, tags_input)
    return post_id, None

def update_post(post_id: int, data: dict) -> tuple[bool, str]:
    title = data.get("title", "").strip()
    if not title:
        return False, "Title is required."

    raw_slug = data.get("slug", "").strip()
    slug = slugify(raw_slug if raw_slug else title)

    download_url = (data.get("download_url") or "").strip()
    if download_url and not validate_download_url(download_url):
        return False, "Invalid Download URL. Only http:// and https:// URLs are allowed."

    yt_id = extract_youtube_id(data.get("youtube_video_id", ""))

    with get_db() as conn:
        cursor = conn.cursor()
        # Slug collision check
        cursor.execute("SELECT id FROM posts WHERE slug = %s AND id != %s;", (slug, post_id))
        if cursor.fetchone():
            slug = f"{slug}-{post_id}"

        cursor.execute("""
            UPDATE posts SET
                title = %s,
                slug = %s,
                summary = %s,
                content = %s,
                thumbnail_url = %s,
                youtube_video_id = %s,
                download_url = %s,
                download_label = %s,
                section_id = %s,
                is_published = %s,
                is_featured = %s,
                seo_title = %s,
                seo_description = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (
            title,
            slug,
            data.get("summary", "").strip(),
            data.get("content", "").strip(),
            data.get("thumbnail_url", "").strip(),
            yt_id,
            download_url,
            data.get("download_label", "DOWNLOAD FILE").strip() or "DOWNLOAD FILE",
            int(data["section_id"]) if data.get("section_id") else None,
            1 if data.get("is_published") else 0,
            1 if data.get("is_featured") else 0,
            data.get("seo_title", "").strip(),
            data.get("seo_description", "").strip(),
            post_id
        ))

    tags_input = data.get("tags", "")
    set_post_tags(post_id, tags_input)
    return True, None

def delete_post(post_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM posts WHERE id = %s;", (post_id,))

def increment_post_view(post_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET view_count = view_count + 1 WHERE id = %s;", (post_id,))

def increment_post_download(post_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET download_count = download_count + 1 WHERE id = %s;", (post_id,))
