import type { components } from "./schema";

type Schemas = components["schemas"];
export type PriceRequest = Schemas["PriceRequest"];
export type PriceResponse = Schemas["PriceResponse"];
export type GreekOut = Schemas["GreekOut"];
export type GreekKey = GreekOut["key"];
export type MetaResponse = Schemas["MetaResponse"];
export type OptionType = Schemas["EuropeanOptionIn"]["option_type"];
