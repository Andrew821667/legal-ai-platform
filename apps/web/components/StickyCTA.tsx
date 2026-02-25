"use client";

import { useEffect, useState } from 'react';
import { MessageCircle } from 'lucide-react';

export default function StickyCTA() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      // Show button after scrolling 300px
      if (window.scrollY > 300) {
        setIsVisible(true);
      } else {
        setIsVisible(false);
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <a
      href="https://t.me/legal_ai_helper_new_bot"
      target="_blank"
      rel="noopener noreferrer"
      className={`fixed bottom-8 right-8 z-50 bg-amber-600 hover:bg-amber-700 text-white font-semibold px-6 py-4 rounded-full shadow-2xl transition-all duration-300 transform hover:scale-110 flex items-center gap-3 group ${
        isVisible ? 'translate-y-0 opacity-100' : 'translate-y-20 opacity-0 pointer-events-none'
      }`}
    >
      <MessageCircle className="w-6 h-6 group-hover:animate-bounce" />
      <span className="hidden md:inline">Связаться с нами</span>
      <div className="absolute inset-0 rounded-full bg-amber-400 opacity-0 group-hover:opacity-20 transition-opacity"></div>
      <div className="absolute -inset-1 bg-amber-400 rounded-full opacity-20 animate-ping"></div>
    </a>
  );
}
