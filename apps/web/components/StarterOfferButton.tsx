"use client";

import { trackStarterOfferSelection } from "@/lib/lead-attribution";
import {
  getStarterOffer,
  STARTER_OFFER_EVENT,
  type StarterOfferId,
} from "@/lib/starter-offers";

type StarterOfferButtonProps = {
  offerId: StarterOfferId;
  targetId: "lead-form" | "legal-help-form";
  label: string;
  className: string;
};

export default function StarterOfferButton({
  offerId,
  targetId,
  label,
  className,
}: StarterOfferButtonProps) {
  const chooseOffer = () => {
    const offer = getStarterOffer(offerId);
    if (!offer) return;

    trackStarterOfferSelection(offer);
    window.dispatchEvent(
      new CustomEvent(STARTER_OFFER_EVENT, { detail: { offerId } }),
    );
    document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <button type="button" onClick={chooseOffer} className={className}>
      {label}
    </button>
  );
}
