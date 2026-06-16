async function getBase64(file: Blob, callback: Function) {
  const reader = new FileReader();
  reader.onload = () => callback(null, reader.result);
  reader.onerror = (error) => callback(error);
  reader.readAsDataURL(file);
}

function formatNumberIndian(num: number) {
  try {
    if (!num) {
      return 0;
    }

    // Split into integer and decimal parts
    let [integerPart, decimalPart] = num.toString().split('.');

    let reversedInt = integerPart.split('').reverse();

    // Group the digits: first group of 3, then groups of 2
    let formattedReversed = [];
    for (let i = 0; i < reversedInt.length; i++) {
      formattedReversed.push(reversedInt[i]);
      // Add a comma after the first 3 digits, then every 2 digits
      if ((i === 2 || (i > 2 && (i - 2) % 2 === 0)) && i !== reversedInt.length - 1) {
        formattedReversed.push(',');
      }
    }
    // Reverse back to get the final formatted integer part
    let formattedInt = formattedReversed.reverse().join('');
    // Append the decimal part if it exists
    return decimalPart ? `${formattedInt}.${decimalPart}` : formattedInt;
  } catch (error) {
    console.error('Error formatting number:', error);
    return null;
  }
}
const base64toBlob = (data: string, pdfContentType: string) => {
  // const base64WithoutPrefix = data.substr(`data:${pdfContentType};base64,`.length);
  const bytes = atob(data);
  let length = bytes.length;
  let out = new Uint8Array(length);

  while (length--) {
    out[length] = bytes.charCodeAt(length);
  }

  return new Blob([out], { type: pdfContentType });
};

export { getBase64, formatNumberIndian, base64toBlob };
