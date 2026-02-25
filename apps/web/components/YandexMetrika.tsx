'use client';

import Script from 'next/script';

interface YandexMetrikaProps {
  counterId: string;
}

/**
 * Компонент Yandex Metrika
 *
 * Устанавливает счетчик Яндекс.Метрики на сайт для сбора аналитики.
 *
 * @param counterId - ID счетчика из Яндекс.Метрики (8-значное число)
 */
export default function YandexMetrika({ counterId }: YandexMetrikaProps) {
  // Если нет ID счетчика - не показываем скрипт
  if (!counterId) {
    return null;
  }

  return (
    <>
      {/* Yandex.Metrika counter */}
      <Script
        id="yandex-metrika"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
            (function(m,e,t,r,i,k,a){
              m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
              m[i].l=1*new Date();
              for (var j = 0; j < document.scripts.length; j++) {
                if (document.scripts[j].src === r) { return; }
              }
              k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
            })
            (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");

            ym(${counterId}, "init", {
              clickmap:true,
              trackLinks:true,
              accurateTrackBounce:true,
              webvisor:true
            });
          `,
        }}
      />

      {/* NoScript fallback */}
      <noscript>
        <div>
          <img
            src={`https://mc.yandex.ru/watch/${counterId}`}
            style={{ position: 'absolute', left: '-9999px' }}
            alt=""
          />
        </div>
      </noscript>
    </>
  );
}
