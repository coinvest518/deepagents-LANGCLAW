---
name: blog-post
description: Writes and structures long-form blog posts, creates tutorial outlines, and optimizes content for SEO with cover image generation. Use when the user asks to write a blog post, article, how-to guide, tutorial, technical writeup, thought leadership piece, or long-form content.
---

# Blog Post Writing Skill

## Research First (Required)

**Before writing any blog post, you MUST delegate research:**

1. Use the `task` tool with `subagent_type: "researcher"`
2. In the description, specify BOTH the topic AND where to save:

```
task(
    subagent_type="researcher",
    description="Research [TOPIC]. Save findings to research/[slug].md"
)
```

Example:
```
task(
    subagent_type="researcher",
    description="Research the current state of AI agents in 2025. Save findings to research/ai-agents-2025.md"
)
```

3. After research completes, read the findings file before writing

## Output Structure (Required)

**Every blog post MUST have both a post AND a cover image:**

```
blogs/
└── <slug>/
    ├── post.md        # The blog post content
    └── hero.png       # REQUIRED: Generated cover image
```

Example: A post about "AI Agents in 2025" → `blogs/ai-agents-2025/`

**You MUST complete both steps:**
1. Write the post to `blogs/<slug>/post.md`
2. Generate a cover image using `generate_image` and save to `blogs/<slug>/hero.png`

**A blog post is NOT complete without its cover image.**

## Blog Post Structure

Every blog post should follow this structure:

### 1. Hook (Opening)
- Start with a compelling question, statistic, or statement
- Make the reader want to continue
- Keep it to 2-3 sentences

### 2. Context (The Problem)
- Explain why this topic matters
- Describe the problem or opportunity
- Connect to the reader's experience

### 3. Main Content (The Solution)
- Break into 3-5 main sections with H2 headers
- Each section covers one key point
- Include code examples, diagrams, or screenshots where helpful
- Use bullet points for lists

### 4. Practical Application
- Show how to apply the concepts
- Include step-by-step instructions if applicable
- Provide code snippets or templates

### 5. Conclusion & CTA
- Summarize key takeaways (3 bullets max)
- End with a clear call-to-action
- Link to related resources

## Cover Image Generation

After writing the post, generate a cover image using the `generate_cover` tool:

```
generate_cover(prompt="A detailed description of the image...", slug="your-blog-slug")
```

The tool saves the image to `blogs/<slug>/hero.png`.

## SEO Considerations

- Include the main keyword in the title and first paragraph
- Use the keyword naturally 3-5 times throughout
- Keep the title under 60 characters
- Write a meta description (150-160 characters)

## Quality Checklist

Before finishing:
- [ ] Post saved to `blogs/<slug>/post.md`
- [ ] Hero image generated at `blogs/<slug>/hero.png`
- [ ] Hook grabs attention in first 2 sentences
- [ ] Each section has a clear purpose
- [ ] Conclusion summarizes key points
- [ ] CTA tells reader what to do next
