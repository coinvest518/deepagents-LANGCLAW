#!/usr/bin/env python3
"""
create_project.py — scaffold a Remotion video project.

Usage:
  python create_project.py --title "My Video" --duration 10 --fps 30
  python create_project.py --title "TikTok" --duration 15 --template tiktok
  python create_project.py --list-templates
"""
import argparse
import json
import os
import subprocess
import sys
import textwrap

TEMPLATES = {
    "default":   {"width": 1920, "height": 1080, "desc": "Landscape 16:9"},
    "tiktok":    {"width": 1080, "height": 1920, "desc": "TikTok/Reels 9:16"},
    "square":    {"width": 1080, "height": 1080, "desc": "Instagram square 1:1"},
    "youtube":   {"width": 1920, "height": 1080, "desc": "YouTube 16:9"},
    "twitter":   {"width": 1280, "height":  720, "desc": "Twitter/X 16:9"},
    "slideshow": {"width": 1920, "height": 1080, "desc": "Slideshow 16:9"},
}


def list_templates():
    print("Available templates:")
    for name, info in TEMPLATES.items():
        print(f"  {name:12} {info['width']}x{info['height']}  — {info['desc']}")


def create_project(title: str, duration: int, fps: int, width: int, height: int,
                   template: str, out_dir: str):
    safe_name = title.lower().replace(" ", "-").replace("_", "-")
    project_dir = os.path.join(out_dir, safe_name)
    os.makedirs(os.path.join(project_dir, "src"), exist_ok=True)

    frames = duration * fps

    # package.json
    pkg = {
        "name": safe_name,
        "version": "1.0.0",
        "scripts": {
            "start": "remotion studio",
            "build": "remotion render",
            "render": f"remotion render src/index.ts MyComposition out/{safe_name}.mp4"
        },
        "dependencies": {
            "remotion": "^4.0.0",
            "@remotion/cli": "^4.0.0",
            "@remotion/renderer": "^4.0.0",
            "react": "^18.0.0",
            "react-dom": "^18.0.0"
        },
        "devDependencies": {
            "@types/react": "^18.0.0",
            "typescript": "^5.0.0"
        }
    }
    with open(os.path.join(project_dir, "package.json"), "w") as f:
        json.dump(pkg, f, indent=2)

    # tsconfig.json
    tsconfig = {
        "compilerOptions": {
            "lib": ["dom", "es2022"],
            "module": "commonjs",
            "target": "ES2022",
            "strict": True,
            "outDir": "./dist",
            "jsx": "react",
            "esModuleInterop": True
        },
        "include": ["src"]
    }
    with open(os.path.join(project_dir, "tsconfig.json"), "w") as f:
        json.dump(tsconfig, f, indent=2)

    # src/index.ts — register composition
    index_ts = textwrap.dedent(f"""\
        import {{ registerRoot }} from 'remotion';
        import {{ RemotionRoot }} from './Root';
        registerRoot(RemotionRoot);
    """)
    with open(os.path.join(project_dir, "src", "index.ts"), "w") as f:
        f.write(index_ts)

    # src/Root.tsx — root with composition
    root_tsx = textwrap.dedent(f"""\
        import {{ Composition }} from 'remotion';
        import {{ MyComposition }} from './Composition';

        export const RemotionRoot: React.FC = () => {{
            return (
                <>
                    <Composition
                        id="MyComposition"
                        component={{MyComposition}}
                        durationInFrames={{{frames}}}
                        fps={{{fps}}}
                        width={{{width}}}
                        height={{{height}}}
                        defaultProps={{{{ title: "{title}" }}}}
                    />
                </>
            );
        }};
    """)
    with open(os.path.join(project_dir, "src", "Root.tsx"), "w") as f:
        f.write(root_tsx)

    # src/Composition.tsx — main video component
    if template == "tiktok":
        comp = _tiktok_template(title, fps, frames)
    elif template == "slideshow":
        comp = _slideshow_template(title, fps, frames)
    else:
        comp = _default_template(title, fps, frames)

    with open(os.path.join(project_dir, "src", "Composition.tsx"), "w") as f:
        f.write(comp)

    print(f"Project created: {project_dir}")
    print(f"  Template : {template} ({width}x{height})")
    print(f"  Duration : {duration}s ({frames} frames @ {fps}fps)")
    print()
    print("Next steps:")
    print(f"  1. cd {project_dir}")
    print(f"  2. npm install")
    print(f"  3. Edit src/Composition.tsx to customise the video")
    print(f"  4. python ../render_video.py --project {project_dir} --out video.mp4")
    print()
    print("Or preview live:")
    print(f"  cd {project_dir} && npx remotion studio")

    return project_dir


def _default_template(title: str, fps: int, frames: int) -> str:
    return textwrap.dedent(f"""\
        import {{ AbsoluteFill, spring, useCurrentFrame, useVideoConfig, interpolate }} from 'remotion';

        interface Props {{ title: string }}

        export const MyComposition: React.FC<Props> = ({{ title }}) => {{
            const frame = useCurrentFrame();
            const {{ fps, durationInFrames }} = useVideoConfig();

            // Fade in over first 30 frames
            const opacity = interpolate(frame, [0, 30], [0, 1], {{ extrapolateRight: 'clamp' }});

            // Title scale spring
            const scale = spring({{ frame, fps, config: {{ damping: 12, stiffness: 200 }} }});

            return (
                <AbsoluteFill style={{{{ backgroundColor: '#0f0f1a', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}}}>
                    <div style={{{{
                        opacity,
                        transform: `scale(${{scale}})`,
                        color: '#ffffff',
                        fontSize: 80,
                        fontWeight: 'bold',
                        fontFamily: 'sans-serif',
                        textAlign: 'center',
                        padding: 40,
                    }}}}>
                        {{title}}
                    </div>
                    <div style={{{{ color: '#888', fontSize: 24, fontFamily: 'sans-serif', opacity }}}}>
                        Frame {{frame}} / {frames}
                    </div>
                </AbsoluteFill>
            );
        }};
    """)


def _tiktok_template(title: str, fps: int, frames: int) -> str:
    return textwrap.dedent(f"""\
        import {{ AbsoluteFill, spring, useCurrentFrame, useVideoConfig, interpolate, Sequence }} from 'remotion';

        interface Props {{ title: string }}

        export const MyComposition: React.FC<Props> = ({{ title }}) => {{
            const frame = useCurrentFrame();
            const {{ fps }} = useVideoConfig();

            const slideUp = spring({{ frame, fps, config: {{ damping: 14, stiffness: 180 }} }});
            const opacity = interpolate(frame, [0, 20], [0, 1], {{ extrapolateRight: 'clamp' }});

            return (
                <AbsoluteFill style={{{{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}}}>
                    {{/* Background pattern */}}
                    <div style={{{{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.03) 0%, transparent 70%)' }}}} />

                    {{/* Main content */}}
                    <div style={{{{
                        transform: `translateY(${{(1 - slideUp) * 100}}px)`,
                        opacity,
                        textAlign: 'center',
                        padding: '0 60px',
                    }}}}>
                        <div style={{{{ fontSize: 56, fontWeight: 900, color: '#fff', fontFamily: 'sans-serif', lineHeight: 1.2, marginBottom: 24 }}}}>
                            {{title}}
                        </div>
                        <div style={{{{ width: 60, height: 4, background: '#e94560', margin: '0 auto', borderRadius: 2 }}}} />
                    </div>

                    {{/* Bottom CTA */}}
                    <Sequence from={{{{Math.floor({frames} * 0.7)}}}}>
                        <div style={{{{ position: 'absolute', bottom: 120, fontSize: 28, color: '#e94560', fontFamily: 'sans-serif', fontWeight: 700 }}}}>
                            ↓ Follow for more
                        </div>
                    </Sequence>
                </AbsoluteFill>
            );
        }};
    """)


def _slideshow_template(title: str, fps: int, frames: int) -> str:
    slides_per_video = max(3, frames // (fps * 3))
    frames_per_slide = frames // slides_per_video

    return textwrap.dedent(f"""\
        import {{ AbsoluteFill, Sequence, spring, useCurrentFrame, useVideoConfig }} from 'remotion';

        const SLIDES = [
            {{ heading: "{title}", body: "Edit this slide in src/Composition.tsx", bg: '#1a1a2e' }},
            {{ heading: "Point Two", body: "Replace with your content", bg: '#16213e' }},
            {{ heading: "Conclusion", body: "Add your call to action here", bg: '#0f3460' }},
        ];

        const Slide: React.FC<{{ heading: string; body: string; bg: string }}> = ({{ heading, body, bg }}) => {{
            const frame = useCurrentFrame();
            const {{ fps }} = useVideoConfig();
            const scale = spring({{ frame, fps, config: {{ damping: 14 }} }});
            return (
                <AbsoluteFill style={{{{ background: bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', padding: 80 }}}}>
                    <div style={{{{ transform: `scale(${{scale}})`, textAlign: 'center' }}}}>
                        <div style={{{{ fontSize: 72, fontWeight: 900, color: '#fff', fontFamily: 'sans-serif', marginBottom: 32 }}}}>{{heading}}</div>
                        <div style={{{{ fontSize: 36, color: '#ccc', fontFamily: 'sans-serif' }}}}>{{body}}</div>
                    </div>
                </AbsoluteFill>
            );
        }};

        interface Props {{ title: string }}
        export const MyComposition: React.FC<Props> = () => {{
            return (
                <AbsoluteFill>
                    {{SLIDES.map((slide, i) => (
                        <Sequence key={{i}} from={{{{i * {frames_per_slide}}}}} durationInFrames={{{{{frames_per_slide}}}}}>
                            <Slide {{...slide}} />
                        </Sequence>
                    ))}}
                </AbsoluteFill>
            );
        }};
    """)


def main():
    parser = argparse.ArgumentParser(description="Scaffold a Remotion video project")
    parser.add_argument("--title", default="My Video", help="Video title")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--width", type=int, default=0, help="Width in px (overrides template)")
    parser.add_argument("--height", type=int, default=0, help="Height in px (overrides template)")
    parser.add_argument("--template", default="default", choices=list(TEMPLATES.keys()), help="Video template")
    parser.add_argument("--out-dir", default=os.environ.get("REMOTION_PROJECT_DIR", "./remotion-projects"), help="Parent directory for project")
    parser.add_argument("--list-templates", action="store_true", help="List available templates")
    args = parser.parse_args()

    if args.list_templates:
        list_templates()
        return

    tmpl = TEMPLATES[args.template]
    width = args.width or tmpl["width"]
    height = args.height or tmpl["height"]

    create_project(
        title=args.title,
        duration=args.duration,
        fps=args.fps,
        width=width,
        height=height,
        template=args.template,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()