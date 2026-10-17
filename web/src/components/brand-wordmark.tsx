import Image from "next/image";

import { cn } from "@/lib/utils";

export function BrandWordmark({ className }: { className?: string }) {
  return (
    <Image
      src="/brand/wordmark.svg"
      alt="WSARTEX"
      width={880}
      height={160}
      unoptimized
      className={cn("h-auto w-40 dark:invert", className)}
    />
  );
}
