import { faqData } from "@/lib/faqData";

interface FAQStructuredDataProps {
  siteUrl?: string;
}

export default function FAQStructuredData({
  siteUrl = "https://legalaipro.ru",
}: FAQStructuredDataProps) {
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "@id": `${siteUrl}/#faq`,
    mainEntity: faqData.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}
