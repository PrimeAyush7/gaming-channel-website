import re
import html
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
        where_clauses.append("p.is_featured = ?")
        params.append(1 if is_featured else 0)

    if section_id:
        where_clauses.append("p.section_id = ?")
        params.append(section_id)
    elif section_slug:
        where_clauses.append("s.slug = ?")
        params.append(section_slug)

    if tag_slug:
        where_clauses.append("""
            p.id IN (
                SELECT pt.post_id FROM post_tags pt
                JOIN tags t ON pt.tag_id = t.id
                WHERE t.slug = ?
            )
        """)
        params.append(tag_slug.strip().lower())

    if search_query:
        search_term = f"%{search_query.strip()}%"
        where_clauses.append("""
            (
                p.title LIKE ? OR 
                p.content LIKE ? OR 
                p.summary LIKE ? OR
                s.name LIKE ? OR
                p.id IN (
                    SELECT pt2.post_id FROM post_tags pt2
                    JOIN tags t2 ON pt2.tag_id = t2.id
                    WHERE t2.name LIKE ? OR t2.slug LIKE ?
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
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]

        # Select rows
        query_sql = f"""
            SELECT p.*, s.name AS section_name, s.slug AS section_slug, s.icon AS section_icon
            FROM posts p
            LEFT JOIN sections s ON p.section_id = s.id
            {where_sql}
            ORDER BY p.is_featured DESC, p.published_at DESC, p.id DESC
            LIMIT ? OFFSET ?;
        """
        cursor.execute(query_sql, params + [per_page, offset])
        rows = [dict(r) for r in cursor.fetchall()]

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
            WHERE p.slug = ? {pub_cond};
        """, (slug.strip(),))
        row = cursor.fetchone()
        if not row:
            return None
        post = dict(row)
        post["tags"] = get_tags_for_post(post["id"])
        return post

def get_post_by_id(post_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.name AS section_name, s.slug AS section_slug, s.icon AS section_icon
            FROM posts p
            LEFT JOIN sections s ON p.section_id = s.id
            WHERE p.id = ?;
        """, (post_id,))
        row = cursor.fetchone()
        if not row:
            return None
        post = dict(row)
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
            LIMIT ?;
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]

def get_related_posts(post_id: int, section_id: int, limit: int = 4):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.name AS section_name, s.slug AS section_slug
            FROM posts p
            LEFT JOIN sections s ON p.section_id = s.id
            WHERE p.id != ? AND p.is_published = 1 AND (p.section_id = ? OR p.section_id IS NOT NULL)
            ORDER BY (p.section_id = ?) DESC, p.published_at DESC
            LIMIT ?;
        """, (post_id, section_id, section_id, limit))
        return [dict(r) for r in cursor.fetchall()]

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
        cursor.execute("SELECT id FROM posts WHERE slug = ?;", (slug,))
        if cursor.fetchone():
            count = 1
            orig = slug
            while True:
                slug = f"{orig}-{count}"
                cursor.execute("SELECT id FROM posts WHERE slug = ?;", (slug,))
                if not cursor.fetchone():
                    break
                count += 1

        cursor.execute("""
            INSERT INTO posts (
                title, slug, summary, content, thumbnail_url,
                youtube_video_id, download_url, download_label,
                section_id, is_published, is_featured,
                seo_title, seo_description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
        post_id = cursor.lastrowid
        
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
        cursor.execute("SELECT id FROM posts WHERE slug = ? AND id != ?;", (slug, post_id))
        if cursor.fetchone():
            slug = f"{slug}-{post_id}"

        cursor.execute("""
            UPDATE posts SET
                title = ?,
                slug = ?,
                summary = ?,
                content = ?,
                thumbnail_url = ?,
                youtube_video_id = ?,
                download_url = ?,
                download_label = ?,
                section_id = ?,
                is_published = ?,
                is_featured = ?,
                seo_title = ?,
                seo_description = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
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
        cursor.execute("DELETE FROM posts WHERE id = ?;", (post_id,))

def increment_post_view(post_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET view_count = view_count + 1 WHERE id = ?;", (post_id,))

def increment_post_download(post_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET download_count = download_count + 1 WHERE id = ?;", (post_id,))
