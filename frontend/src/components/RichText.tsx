import React from "react";

type Segment = { type: "text" | "strong" | "em" | "code"; value: string };

function parseSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  const pattern = /\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    if (match[1]) {
      segments.push({ type: "strong", value: match[1] });
    } else if (match[2]) {
      segments.push({ type: "em", value: match[2] });
    } else if (match[3]) {
      segments.push({ type: "code", value: match[3] });
    }
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push({ type: "text", value: text.slice(lastIndex) });
  }

  return segments.length ? segments : [{ type: "text", value: text }];
}

export function RichText({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  const segments = parseSegments(text);

  return (
    <p className={className}>
      {segments.map((segment, index) => {
        const key = `${segment.type}-${index}`;
        switch (segment.type) {
          case "strong":
            return <strong key={key}>{segment.value}</strong>;
          case "em":
            return <em key={key}>{segment.value}</em>;
          case "code":
            return <code key={key}>{segment.value}</code>;
          default:
            return <React.Fragment key={key}>{segment.value}</React.Fragment>;
        }
      })}
    </p>
  );
}
