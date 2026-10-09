import React from "react";
import { Composition } from "remotion";
import { Film } from "./Film";
import { FPS } from "./time";

export const Root: React.FC = () => (
  <Composition id="Hearsay" component={Film} durationInFrames={60 * FPS} fps={FPS} width={1920} height={1080} />
);
