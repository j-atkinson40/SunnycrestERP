// Wilbert CDN preview images for Legacy Series prints.
// Shared by proof-generator.tsx and library.tsx.
// Note: Not every print has a Wilbert CDN preview. Missing ones return null
// from getPrintImageUrl() and fall back to gray placeholder in the UI.

const _CDN = "https://www.wilbert.com/assets/1/14"

export const STANDARD_PRINT_IMAGES: Record<string, string> = {
  // Religious & Spiritual
  "American Flag": `${_CDN}/WLP-AmFlag-L2-750.jpg`,
  "Crucifix — Bible": `${_CDN}/WLP-Crucifix-Bible-L2-750.jpg`,
  "Forever in God's Care": `${_CDN}/WLP-ForeverGodsCareCross-L2-750.jpg`,
  "Going Home": `${_CDN}/WLP-GoingHome-L2-750.jpg`,
  "Irish Blessing": `${_CDN}/WLP-IrishBlessing-L2-750.jpg`,
  "Jesus": `${_CDN}/WLP-Jesus-L2-750.jpg`,
  "Jesus at Dawn": `${_CDN}/WLP-Jesus-dwn-L2-750.jpg`,
  "Jewish 1": `${_CDN}/WLP-Jewish-L2-750.jpg`,
  "Three Crosses": `${_CDN}/WLP-3Crosses-L2-750.jpg`,
  "Pieta": `${_CDN}/WLP-Pieta-L2-750.jpg`,

  // Nature & Landscapes
  "Autumn Lake": `${_CDN}/WLP-AutumnLake-L2-750.jpg`,
  "Bridge 1": `${_CDN}/WLP-Bridge-1-L2-750.jpg`,
  "Bridge 2": `${_CDN}/WLP-Bridge-2-L2-750.jpg`,
  "Cardinal": `${_CDN}/WLP-Cardinal-L2-750.jpg`,
  "Clouds": `${_CDN}/WLP-Clouds-L2-750.jpg`,
  "Country Road": `${_CDN}/WLP-CountryRoad-L2-750.jpg`,
  "Dock": `${_CDN}/WLP-Dock-L2-750.jpg`,
  "Footprints": `${_CDN}/WLP-Footprints-L2-750.jpg`,
  "Footprints with Poem": `${_CDN}/WLP-FootprintsPoem-L2-750.jpg`,
  "Green Field & Barn": `${_CDN}/WLP-FieldRBarn-L2-750.jpg`,
  "Lighthouse": `${_CDN}/WLP-Lighthouse-L2-750.jpg`,
  "Red Barn": `${_CDN}/WLP-RedBarn-L2-750.jpg`,
  "Sunrise-Sunset": `${_CDN}/WLP-Sunrise-L2-750.jpg`,
  "Sunrise-Sunset 2": `${_CDN}/WLP-Sunset-L2-750.jpg`,
  "Tropical": `${_CDN}/WLP-Tropical-Island-L2-750.jpg`,
  "Whitetail Buck": `${_CDN}/WLP-WhitetailBuck-L2-750.jpg`,

  // Floral
  "Roses on Silk": `${_CDN}/WLP-Roses_On_Silk-L2-750.jpg`,
  "Red Roses": `${_CDN}/WLP-R-Roses-L2-750.jpg`,
  "Yellow Roses": `${_CDN}/WLP-Y-Roses-L2-750.jpg`,

  // Occupations & Hobbies
  "Combine": `${_CDN}/WLP-Combine-L2-750.jpg`,
  "Corn": `${_CDN}/WLP-Corn-L2-750.jpg`,
  "EMT": `${_CDN}/WLP-EMT-L2-750.jpg`,
  "Farm Field with Tractor": `${_CDN}/WLP-SunsetFarmFieldTractor-L2-750.jpg`,
  "Father 1": `${_CDN}/WLP-Father-1-L2-750.jpg`,
  "Father 2": `${_CDN}/WLP-Father-2-L2-750.jpg`,
  "Firefighter": `${_CDN}/WLP-Firefighter-L2-750.jpg`,
  "Fisherman": `${_CDN}/WLP-Fisherman-L2-750.jpg`,
  "Fisherman with Dog": `${_CDN}/WLP-Fisherman-Dog-L2-750.jpg`,
  "Golf Course": `${_CDN}/WLP-GolfCourse-L2-750.jpg`,
  "Golfer": `${_CDN}/WLP-Golfer-L2-750.jpg`,
  "Gone Fishing": `${_CDN}/WLP-GoneFishin-L2-750.jpg`,
  "Horses": `${_CDN}/WLP-Horse-L2-750.jpg`,
  "Mother 1": `${_CDN}/WLP-Mother-1-L2-750.jpg`,
  "Mother 2": `${_CDN}/WLP-Mother-2-L2-750.jpg`,
  "Motorcycle 1": `${_CDN}/WLP-Motorcycle_1-L2-750.jpg`,
  "Motorcycle 2": `${_CDN}/WLP-Motorcycle_2-L2-750.jpg`,
  "Music": `${_CDN}/WLP-Music-L2-750.jpg`,
  "Police": `${_CDN}/WLP-Police-L2-750.jpg`,
  "School": `${_CDN}/WLP-School-L2-750.jpg`,
  "Tobacco Barn": `${_CDN}/WLP-TobBarn-L2-750.jpg`,
  "Tobacco Field": `${_CDN}/WLP-TobaccoField-750.jpg`,
}

export const URN_PRINT_IMAGES: Record<string, string> = {
  "U.S. Flag": `${_CDN}/WLP-UV-AmFlag_L2-750.jpg`,
  "Autumn Lake": `${_CDN}/WLP-UV-AutumnLake_L2-750.jpg`,
  "Bridge 1": `${_CDN}/WLP-UV-Bridge-1_L2-750.jpg`,
  "Bridge 2": `${_CDN}/WLP-UV-Bridge-2_L2-750.jpg`,
  "Cardinal": `${_CDN}/WLP-UV-Cardinal_L2-750.jpg`,
  "Clouds": `${_CDN}/WLP-UV-Clouds_L2-750.jpg`,
  "Combine": `${_CDN}/WLP-UV-Combine_L2-750.jpg`,
  "Corn": `${_CDN}/WLP-UV-Corn_L2-750.jpg`,
  "Country Road": `${_CDN}/WLP-UV-CountryRoad_L2-750.jpg`,
  "Crucifix on Bible": `${_CDN}/WLP-UV-Crucifix-Bible_L2-750.jpg`,
  "Dock": `${_CDN}/WLP-UV-Dock_L2-750.jpg`,
  "EMT": `${_CDN}/WLP-UV-EMT_L2-750.jpg`,
  "Father 1": `${_CDN}/WLP-UV-Father-1_L2-750.jpg`,
  "Father 2": `${_CDN}/WLP-UV-Father-2_L2-750.jpg`,
  "Firefighter": `${_CDN}/WLP-UV-Firefighter_L2-750.jpg`,
  "Fisherman": `${_CDN}/WLP-UV-Fisherman_L2-750.jpg`,
  "Fisherman with Dog": `${_CDN}/WLP-UV-Fisherman-Dog_L2-750.jpg`,
  "Footprints": `${_CDN}/WLP-UV-Footprints_L2-750.jpg`,
  "Going Home": `${_CDN}/WLP-UV-GoingHome_L2-750.jpg`,
  "Golf Course": `${_CDN}/WLP-UV-GolfCourse_L2-750.jpg`,
  "Golfer": `${_CDN}/WLP-UV-Golfer_L2-750.jpg`,
  "Gone Fishing": `${_CDN}/WLP-UV-GoneFishin_L2-750.jpg`,
  "Green Field & Barn": `${_CDN}/WLP-UV-GFieldRBarn_L2-750.jpg`,
  "Horses": `${_CDN}/WLP-UV-Horse_L2-750.jpg`,
  "Irish Blessing": `${_CDN}/WLP-UV-IrishBlessing_L2-750.jpg`,
  "Jesus": `${_CDN}/WLP-UV-Jesus_L2-750.jpg`,
  "Three Crosses": `${_CDN}/WLP-UV-3-Crosses_L2-750.jpg`,
}

/** Look up the Wilbert CDN preview image for a print name. */
export function getPrintImageUrl(printName: string | null): string | null {
  if (!printName) return null
  return STANDARD_PRINT_IMAGES[printName] || URN_PRINT_IMAGES[printName] || null
}
