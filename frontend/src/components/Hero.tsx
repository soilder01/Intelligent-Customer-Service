import { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import anime from 'animejs';
import type { SceneConfig } from '../types';

interface HeroProps { scene: SceneConfig; }

export function Hero({ scene }: HeroProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const ctx = gsap.context(() => {
      gsap.from('.hero-kicker', { y: -12, opacity: 0, duration: 0.7, ease: 'power3.out' });
      gsap.from('.hero-title', { y: 24, opacity: 0, duration: 0.9, delay: 0.08, ease: 'power3.out' });
      gsap.from('.hero-card', { y: 18, opacity: 0, duration: 0.7, stagger: 0.08, delay: 0.2, ease: 'power3.out' });
    }, root);
    const animation = anime({ targets: root.querySelectorAll('.hero-orb'), translateX: [0, 18, -12, 0], translateY: [0, -12, 18, 0], scale: [1, 1.08, 0.96, 1], duration: 6800, loop: true, easing: 'easeInOutSine' });
    return () => { ctx.revert(); animation.pause(); };
  }, [scene.id]);

  return <section className="hero" ref={rootRef} style={{ '--accent-a': scene.gradient[0], '--accent-b': scene.gradient[1] } as React.CSSProperties}>
    <div className="hero-orb orb-a" /><div className="hero-orb orb-b" />
    <div className="hero-copy">
      <p className="hero-kicker">Agentic Service OS · Modern Frontend</p>
      <h1 className="hero-title">{scene.name}<br />智能工作台</h1>
      <p className="hero-desc">{scene.description}。前端工程已独立为 React + TypeScript，支持质量运营、任务追踪、复核闭环和评测样本治理。</p>
      <div className="hero-pills"><span>RAG 引用</span><span>Tool Registry</span><span>Human-in-loop</span><span>Quality Gate</span></div>
    </div>
    <div className="hero-stack">
      {scene.tools.map((tool) => <div className="hero-card" key={tool}><span />{tool}</div>)}
    </div>
  </section>;
}
