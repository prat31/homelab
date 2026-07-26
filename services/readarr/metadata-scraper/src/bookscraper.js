import * as cheerio from 'cheerio';

const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15";

export const getBook = async (id) => {
    const scrapeURL = `https://www.goodreads.com/book/show/${id}`;
    const response = await fetch(scrapeURL, {
        method: "GET",
        headers: new Headers({
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }),
    });
    const htmlString = await response.text();
    const $ = cheerio.load(htmlString);

    // Try multiple selectors for title
    const title = $('[data-testid="bookTitle"]').text().trim()
        || $('h1.BookPageTitleSection__title').text().trim()
        || $('meta[property="og:title"]').attr('content')
        || '';

    // Try multiple selectors for author
    let author = $(".ContributorLinksList > span > a")
        .map((i, el) => {
            const $el = $(el);
            const name = $el.find("span").text().trim();
            const url = $el.attr("href") || '';
            const id = url.substring(url.lastIndexOf('/') + 1).split('.')[0];
            return { id: parseInt(id) || 0, name, url };
        }).toArray();

    // Fallback: try other author selectors
    if (author.length === 0) {
        author = $('[data-testid="name"]')
            .map((i, el) => {
                const $el = $(el);
                const name = $el.text().trim();
                const href = $el.attr('href') || $el.closest('a').attr('href') || '';
                const id = href.substring(href.lastIndexOf('/') + 1).split('.')[0];
                return { id: parseInt(id) || 0, name, url: href };
            }).toArray();
    }

    // Fallback: try meta tag for author
    if (author.length === 0) {
        const authorName = $('meta[name="author"]').attr('content')
            || $('meta[property="books:author"]').attr('content')
            || '';
        if (authorName) {
            author = [{ id: 0, name: authorName, url: '' }];
        }
    }

    // Fallback: parse from page text (Author: Name pattern)
    if (author.length === 0) {
        const authorText = $('a[href*="/author/show/"]').first();
        if (authorText.length) {
            const name = authorText.text().trim();
            const url = authorText.attr('href') || '';
            const id = url.substring(url.lastIndexOf('/') + 1).split('.')[0];
            author = [{ id: parseInt(id) || 0, name, url }];
        }
    }

    const cover = $(".ResponsiveImage").attr("src")
        || $('meta[property="og:image"]').attr('content')
        || '';
    const workURL = $('meta[property="og:url"]').attr('content') || scrapeURL;
    const rating = $("div.RatingStatistics__rating").text().slice(0, 4)
        || $('[itemprop="ratingValue"]').first().text()
        || '0';
    const ratingCount = ($('[data-testid="ratingsCount"]').text().split("rating")[0] || '0').replace(/[^\d]/g, '');
    const desc = $('[data-testid="description"]').text()
        || $('[itemprop="description"]').text()
        || $('meta[property="og:description"]').attr('content')
        || '';
    const genres = $('[data-testid="genresList"] > ul > span > span')
        .map((i, el) => $(el).find("span").text().replace("Genres", "")).get();
    const bookEdition = $('[data-testid="pagesFormat"]').text()
        || '';

    const authorInfo = author.length > 0
        ? { id: author[0].id, name: author[0].name, url: author[0].url }
        : { id: 0, name: "Unknown", url: "" };

    const realBook = {
        Asin: "",
        AverageRating: parseFloat(rating) || 0,
        Contributors: [{ ForeignId: authorInfo.id, Role: "Author" }],
        Description: desc,
        EditionInformation: bookEdition,
        ForeignId: parseInt(id),
        Format: "",
        ImageUrl: cover,
        IsEbook: true,
        Isbn13: null,
        Language: "eng",
        NumPages: null,
        Publisher: "",
        RatingCount: parseInt(ratingCount) || 0,
        ReleaseDate: null,
        Title: title,
        Url: workURL,
    };

    console.log(`Scraped book ${id}: "${title}" by ${authorInfo.name}`);

    return { work: realBook, author };
};

export default getBook;
