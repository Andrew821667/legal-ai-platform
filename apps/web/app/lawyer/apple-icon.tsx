import { ImageResponse } from "next/og";

/**
 * Иконка при добавлении рабочего места на экран «Домой».
 *
 * SVG-иконка сайта (app/icon.svg) не годится напрямую: apple-touch-icon
 * надёжно растеризуется только из растра, а конвертировать SVG в PNG на
 * боевом хосте нечем. next/og рисует тот же мотив — тёмный квадрат, галочка
 * градиентом — уже как PNG, без внешних инструментов.
 */
export const runtime = "edge";
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a1423",
          borderRadius: 40,
        }}
      >
        <svg width="120" height="120" viewBox="0 0 64 64" fill="none">
          <path
            d="M17 17h26c6 0 9 4 9 9v9"
            stroke="#67e8f9"
            strokeWidth={5}
            strokeLinecap="round"
          />
          <path
            d="M14 25v18c0 6 4 9 10 9h15"
            stroke="#475569"
            strokeWidth={5}
            strokeLinecap="round"
          />
          <path
            d="m21 30 10 13 16-22"
            stroke="#f59e0b"
            strokeWidth={6}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    ),
    size,
  );
}
