"use client";

import { useEffect, useState, useRef } from 'react';
import { MessageCircle, X } from 'lucide-react';

interface MousePosition {
  x: number;
  y: number;
}

export default function FloatingCTA() {
  const [buttonPosition, setButtonPosition] = useState<MousePosition>({ x: 0, y: 0 });
  const [isVisible, setIsVisible] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState<MousePosition>({ x: 0, y: 0 });
  const [wasDragged, setWasDragged] = useState(false);
  const buttonRef = useRef<HTMLAnchorElement>(null);

  // Устанавливаем начальную позицию в правом нижнем углу
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const updatePosition = () => {
      // Начальная позиция в правом нижнем углу с учетом размера кнопки
      const currentButtonWidth = window.innerWidth < 768 ? 80 : 160;
      const currentButtonHeight = window.innerWidth < 768 ? 40 : 80;
      setButtonPosition({
        x: window.innerWidth - currentButtonWidth - 20, // Отступ от края
        y: window.innerHeight - currentButtonHeight - 20
      });
    };

    updatePosition();
    // Показываем кнопку сразу
    setIsVisible(true);

    // Обновляем позицию при изменении размера окна
    window.addEventListener('resize', updatePosition);
    return () => window.removeEventListener('resize', updatePosition);
  }, []);

  // Логика drag & drop (мышь и touch)
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        // Если происходит перемещение - отмечаем что было перетаскивание
        setWasDragged(true);
        setButtonPosition({
          x: e.clientX - dragOffset.x,
          y: e.clientY - dragOffset.y,
        });
      }
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (isDragging && e.touches.length === 1) {
        // Если происходит перемещение - отмечаем что было перетаскивание
        setWasDragged(true);
        const touch = e.touches[0];
        setButtonPosition({
          x: touch.clientX - dragOffset.x,
          y: touch.clientY - dragOffset.y,
        });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    const handleTouchEnd = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.addEventListener('touchmove', handleTouchMove, { passive: false });
      document.addEventListener('touchend', handleTouchEnd);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  }, [isDragging, dragOffset]);

  // Обработчик начала перетаскивания (мышь)
  const handleMouseDown = (e: React.MouseEvent) => {
    setWasDragged(false); // Сбрасываем флаг перетаскивания
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setDragOffset({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    }
    setIsDragging(true);
    e.preventDefault();
  };

  // Обработчик начала перетаскивания (touch)
  const handleTouchStart = (e: React.TouchEvent) => {
    setWasDragged(false); // Сбрасываем флаг перетаскивания
    if (buttonRef.current && e.touches.length === 1) {
      const rect = buttonRef.current.getBoundingClientRect();
      const touch = e.touches[0];
      setDragOffset({
        x: touch.clientX - rect.left,
        y: touch.clientY - rect.top,
      });
    }
    setIsDragging(true);
    e.preventDefault();
  };

  // Обработчик клика - предотвращает переход если было перетаскивание
  const handleClick = (e: React.MouseEvent) => {
    if (wasDragged) {
      e.preventDefault();
      setWasDragged(false); // Сбрасываем флаг после использования
    }
  };

  // Определяем размер кнопки в зависимости от устройства
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const buttonWidth = isMobile ? 80 : 160; // На мобильных - исходный размер, на десктопе - увеличенный
  const buttonHeight = isMobile ? 40 : 80; // Пропорционально уменьшаем высоту

  const constrainedX = typeof window !== 'undefined'
    ? Math.max(buttonWidth / 2, Math.min(window.innerWidth - buttonWidth / 2, buttonPosition.x))
    : buttonPosition.x;
  const constrainedY = typeof window !== 'undefined'
    ? Math.max(buttonHeight / 2, Math.min(window.innerHeight - buttonHeight / 2, buttonPosition.y))
    : buttonPosition.y;

  return (
    <>
      {/* Большая овальная кнопка */}
      <a
        ref={buttonRef}
        href="https://t.me/legal_ai_helper_new_bot"
        target="_blank"
        rel="noopener noreferrer"
        className={`fixed z-50 transition-all duration-300 transform ${
          isMobile ? 'w-20 h-10' : 'w-40 h-20'
        } ${
          isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-0 pointer-events-none'
        } ${
          isHovered ? 'scale-105' : 'scale-100'
        } ${
          isDragging ? 'cursor-grabbing' : 'cursor-pointer'
        }`}
        style={{
          left: constrainedX - buttonWidth / 2,
          top: constrainedY - buttonHeight / 2,
          transition: isDragging ? 'none' : 'transform 0.3s ease',
        }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
        onClick={handleClick}
      >
        {/* Фон с градиентом - овальная форма */}
        <div className="absolute inset-0 bg-gradient-to-br from-amber-400 via-amber-500 to-amber-600 rounded-full shadow-2xl">
          {/* Пульсирующий эффект */}
          <div className="absolute inset-0 bg-amber-300 rounded-full animate-ping opacity-20"></div>

          {/* Свечение при наведении */}
          {isHovered && (
            <div className="absolute inset-0 bg-white rounded-full opacity-30 animate-pulse"></div>
          )}
        </div>

        {/* Иконка и текст */}
        <div className="relative flex items-center justify-center h-full text-white font-semibold px-2">
          <MessageCircle className={`flex-shrink-0 mr-1 ${isMobile ? 'w-4 h-4' : 'w-6 h-6'}`} />
          <span className={`whitespace-nowrap ${isMobile ? 'text-xs' : 'text-sm'}`}>
            {isMobile ? 'Написать' : 'Связаться с нами'}
          </span>
        </div>
      </a>

      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateX(-50%) translateY(-20px); }
          to { opacity: 1; transform: translateX(-50%) translateY(0); }
        }

        @keyframes fadeOut {
          from { opacity: 1; transform: translateX(-50%) translateY(0); }
          to { opacity: 0; transform: translateX(-50%) translateY(-20px); }
        }
      `}</style>
    </>
  );
}
