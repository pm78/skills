# Technical SEO Reference

## Next.js SEO Implementation

### Metadata API (App Router)

```tsx
// app/layout.tsx - Global defaults
export const metadata: Metadata = {
  metadataBase: new URL('https://example.com'),
  title: {
    default: 'Brand Name',
    template: '%s | Brand Name',
  },
  description: 'Default site description',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'Brand Name',
  },
  twitter: {
    card: 'summary_large_image',
  },
  robots: {
    index: true,
    follow: true,
  },
};

// app/blog/[slug]/page.tsx - Per-page dynamic metadata
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const post = await getPost(params.slug);
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      images: [{ url: post.coverImage, width: 1200, height: 630 }],
      type: 'article',
      publishedTime: post.publishedAt,
      authors: [post.author.name],
    },
    alternates: {
      canonical: `/blog/${params.slug}`,
    },
  };
}
```

### Sitemap Generation

```tsx
// app/sitemap.ts
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await getAllPosts();
  const pages = await getAllPages();

  const postEntries = posts.map((post) => ({
    url: `https://example.com/blog/${post.slug}`,
    lastModified: post.updatedAt,
    changeFrequency: 'weekly' as const,
    priority: 0.7,
  }));

  const pageEntries = pages.map((page) => ({
    url: `https://example.com/${page.slug}`,
    lastModified: page.updatedAt,
    changeFrequency: 'monthly' as const,
    priority: 0.8,
  }));

  return [
    { url: 'https://example.com', lastModified: new Date(), changeFrequency: 'daily', priority: 1 },
    ...pageEntries,
    ...postEntries,
  ];
}
```

### robots.txt

```tsx
// app/robots.ts
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/api/', '/admin/', '/private/'],
      },
    ],
    sitemap: 'https://example.com/sitemap.xml',
  };
}
```

### JSON-LD Structured Data Component

```tsx
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

// Usage in a page
<JsonLd data={{
  "@context": "https://schema.org",
  "@type": "Article",
  headline: post.title,
  author: { "@type": "Person", name: post.author },
  datePublished: post.publishedAt,
  dateModified: post.updatedAt,
  image: post.coverImage,
  publisher: {
    "@type": "Organization",
    name: "Brand Name",
    logo: { "@type": "ImageObject", url: "https://example.com/logo.png" },
  },
}} />
```

## Redirect Rules

```tsx
// next.config.ts
const nextConfig = {
  async redirects() {
    return [
      // Permanent redirect (301) - SEO value transfers
      { source: '/old-page', destination: '/new-page', permanent: true },
      // Temporary redirect (302) - no SEO transfer
      { source: '/temp', destination: '/other', permanent: false },
      // Pattern matching
      { source: '/blog/:slug', destination: '/articles/:slug', permanent: true },
    ];
  },
};
```

## Performance Optimization for SEO

### Image Optimization
```tsx
import Image from 'next/image';

<Image
  src="/hero.jpg"
  alt="Descriptive alt text with keyword"
  width={1200}
  height={630}
  priority  // Preload for LCP
  sizes="(max-width: 768px) 100vw, 50vw"
/>
```

### Font Optimization
```tsx
import { Inter } from 'next/font/google';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',  // Prevents CLS from font loading
});
```

## Internal Linking Strategy

- **Hub and spoke model**: Pillar page links to cluster pages and vice versa
- **Contextual links**: Within body content, naturally placed
- **Breadcrumbs**: Show hierarchy, use BreadcrumbList schema
- **Related content**: At bottom of articles
- **Navigation**: Clear, logical site structure
- **Anchor text**: Descriptive, keyword-relevant (not "click here")

## Content Audit Template

| URL | Title | Word Count | Target Keyword | Ranking | Traffic | Action |
|-----|-------|-----------|----------------|---------|---------|--------|
| /page-1 | ... | ... | ... | #12 | 500/mo | Optimize |
| /page-2 | ... | ... | ... | N/A | 0 | Rewrite |
| /page-3 | ... | ... | ... | #3 | 5000/mo | Maintain |
| /page-4 | ... | ... | ... | #45 | 10/mo | Merge/301 |

Actions: Optimize, Rewrite, Maintain, Merge, Remove, Create
