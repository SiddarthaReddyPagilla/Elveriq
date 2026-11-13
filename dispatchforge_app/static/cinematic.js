/** Elveriq landing story. Progressive enhancement; no tracking or network requests. */
(() => {
  'use strict';

  const page = document.querySelector('.cinematic-page');
  if (!page) return;

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const stages = [...page.querySelectorAll('[data-stage]')];
  const photos = [...page.querySelectorAll('[data-stage-photo]')];
  const sceneLabel = page.querySelector('[data-scene-label]');
  const sceneCounter = page.querySelector('[data-scene-counter]');
  const labels = ['RECEIVING DOCK', 'STORAGE AISLES', 'PICK AND PACK', 'DISPATCH BAY'];
  let activeStage = -1;

  function setStage(index) {
    if (!Number.isInteger(index) || index < 0 || index >= stages.length || index === activeStage) return;
    activeStage = index;
    photos.forEach((photo) => photo.classList.toggle('is-active', Number(photo.dataset.stagePhoto) === index));
    if (sceneLabel) sceneLabel.textContent = labels[index] || '';
    if (sceneCounter) sceneCounter.textContent = `${String(index + 1).padStart(2, '0')} / ${String(stages.length).padStart(2, '0')}`;
  }

  setStage(0);

  if ('IntersectionObserver' in window) {
    if (!reduceMotion) {
      page.classList.add('motion-ready');
      const revealObserver = new IntersectionObserver((entries, observer) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-revealed');
            observer.unobserve(entry.target);
          }
        }
      }, { threshold: 0.12, rootMargin: '0px 0px -25px 0px' });
      page.querySelectorAll('[data-reveal]').forEach((element) => revealObserver.observe(element));
    }

    const stageObserver = new IntersectionObserver((entries) => {
      const onScreen = entries.filter((entry) => entry.isIntersecting);
      if (!onScreen.length) return;
      onScreen.sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      setStage(Number(onScreen[0].target.dataset.stage));
    }, { rootMargin: '-26% 0px -26% 0px', threshold: [0, 0.15, 0.3, 0.5] });
    stages.forEach((stage) => stageObserver.observe(stage));
  }

  const statement = page.querySelector('[data-word-reveal]');
  if (statement && !reduceMotion) {
    const words = statement.textContent.trim().split(/\s+/);
    statement.textContent = '';
    const spans = words.map((word, i) => {
      const span = document.createElement('span');
      span.className = 'cinema-word';
      span.textContent = word;
      span.style.transitionDelay = `${Math.min(i * 75, 900)}ms`;
      statement.append(span);
      if (i < words.length - 1) statement.append(document.createTextNode(' '));
      return span;
    });
    if ('IntersectionObserver' in window) {
      const wordObserver = new IntersectionObserver((entries, observer) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          spans.forEach((span) => span.classList.add('is-active'));
          observer.unobserve(entry.target);
        }
      }, { threshold: 0.28 });
      wordObserver.observe(statement);
    } else {
      spans.forEach((span) => span.classList.add('is-active'));
    }
  }

  // Transform-only parallax, with one scheduled animation frame per scroll event.
  const hero = page.querySelector('.cinema-hero');
  const heroImage = page.querySelector('[data-hero-image]');
  if (hero && heroImage && !reduceMotion) {
    let queued = false;
    const onScroll = () => {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(() => {
        queued = false;
        const distance = Math.min(Math.max(window.scrollY || 0, 0), hero.offsetHeight);
        heroImage.style.setProperty('--hero-shift', `${Math.round(distance * 0.12)}px`);
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
  }
})();
