import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig, interpolate, Sequence } from 'remotion';

interface Props { title: string }

export const MyComposition: React.FC<Props> = ({ title }) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    const slideUp = spring({ frame, fps, config: { damping: 14, stiffness: 180 } });
    const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });

    return (
        <AbsoluteFill style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
            {/* Background pattern */}
            <div style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.03) 0%, transparent 70%)' }} />

            {/* Main content */}
            <div style={{
                transform: `translateY(${(1 - slideUp) * 100}px)`,
                opacity,
                textAlign: 'center',
                padding: '0 60px',
            }}>
                <div style={{ fontSize: 56, fontWeight: 900, color: '#fff', fontFamily: 'sans-serif', lineHeight: 1.2, marginBottom: 24 }}>
                    {title}
                </div>
                <div style={{ width: 60, height: 4, background: '#e94560', margin: '0 auto', borderRadius: 2 }} />
            </div>

            {/* Bottom CTA */}
            <Sequence from={Math.floor(90 * 0.7)}>
                <div style={{ position: 'absolute', bottom: 120, fontSize: 28, color: '#e94560', fontFamily: 'sans-serif', fontWeight: 700 }}>
                    ↓ Follow for more
                </div>
            </Sequence>
        </AbsoluteFill>
    );
};
