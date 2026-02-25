'use client';

import Script from 'next/script';

interface GoogleAnalyticsProps {
  measurementId: string;
}

/**
 * Компонент Google Analytics 4
 *
 * Устанавливает счетчик Google Analytics 4 (gtag.js) на сайт для сбора аналитики.
 *
 * @param measurementId - Measurement ID из Google Analytics 4 (формат: G-XXXXXXXXXX)
 */
export default function GoogleAnalytics({ measurementId }: GoogleAnalyticsProps) {
  // Если нет Measurement ID - не показываем скрипт
  if (!measurementId) {
    return null;
  }

  return (
    <>
      {/* Google Analytics 4 - gtag.js */}
      <Script
        strategy="afterInteractive"
        src={`https://www.googletagmanager.com/gtag/js?id=${measurementId}`}
      />

      <Script
        id="google-analytics"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', '${measurementId}', {
              page_path: window.location.pathname,
            });
          `,
        }}
      />
    </>
  );
}
