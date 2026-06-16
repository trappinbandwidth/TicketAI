/**
 * CheckIfNotEmpty is for checking text is empty or not
 * @param text
 * @returns {*|boolean}
 * @constructor
 */
export const CheckIfNotEmpty = (text: string = ''): boolean =>
  !(text == null || /^\s*$/.test(text));

/**
 * ToTitleCase is for convert lines/text into title case
 * @param {string} txt
 * @returns {stargin}
 * @constructor
 */
export const ToTitleCase = (txt: string = ''): string =>
  txt
    .split(' ')
    .map((_i) => _i.slice(0, 1).toUpperCase() + _i.slice(1, _i.length).toLowerCase())
    .join(' ');
