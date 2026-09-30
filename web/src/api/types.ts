import type { components } from "./schema";

type Schemas = components["schemas"];
export type PriceRequest = Schemas["PriceRequest"];
export type PriceResponse = Schemas["PriceResponse"];
export type ProfileRequest = Schemas["ProfileRequest"];
export type ProfileResponse = Schemas["ProfileResponse"];
export type HeatmapRequest = Schemas["HeatmapRequest"];
export type HeatmapResponse = Schemas["HeatmapResponse"];
export type ImpliedVolRequest = Schemas["ImpliedVolRequest"];
export type ImpliedVolResponse = Schemas["ImpliedVolResponse"];
export type GreekOut = Schemas["GreekOut"];
export type GreekKey = GreekOut["key"];
export type MetaResponse = Schemas["MetaResponse"];
export type OptionType = Schemas["EuropeanOptionIn"]["option_type"];
export type ModelType = Schemas["ModelIn"]["type"];
