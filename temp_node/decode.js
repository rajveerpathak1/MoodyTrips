const list = ['ntyYnJyYngjMu0fksa', 'zgLNzxn0', 'l3rVzgf5', 'odeYmJeZnunJse9WEq', 'Ahr0Chm6lY9YywLSA2L0lwfWAs5YywPPDMr1yMv5lMrLDG', 'DxbKyxrL', 'mJC1mty4nZb6vxvyC1q', 'l2fWAs90CMfJA1rYywLUlW', 'Dg9tDhjPBMC', 'l2fWAs9JAgvJA1bouLn0yxr1CY8', 'DhjPBq', 'l2fWAs90CMfPBKHPC3rVCNKV', 'ovLMyu5rEa', 'sM91CM5LEsbKyxrLigLZihjLCxvPCMvKigfUzcbTDxn0igjLigLUierelu1nlvLzwvKGzM9YBwf0lG', 'ue5sig51BwjLCIbPCYbYzxf1AxjLzcbHBMqGBxvZDcbIzsbHihn0CMLUzY4', 'oty2nwLjAMfvvG', 'Agv4', 'ANnVBG', 'l2fWAs9ZzwfYy2HuCMfPBKjLDhDLzw5tDgf0Aw9UCY8', 'C3rYAw5N', 'mtC2otKYnvjbswzoyW', 'qM90AcbMCM9TigfUzcb0BYbZDgf0Aw9UignVzgvZigfYzsbYzxf1AxjLzcbHBMqGBxvZDcbIzsbZDhjPBMDZlG', 'uMvXDwvZDcbMywLSzwq6ia', 'mJu4nNzIEMzvzq', 'BgvUz3rO', 'Aw5JBhvKzxm', 'sw52ywXPzcb0CMfPBIbUDw1IzxiUieL0ig11C3qGyMuGysa1lwnOyxjHy3rLCIbZDhjPBMCU', 'p2HYCZ0', 'BM93', 'mteXntKZmJHqAhbeBuO', 'AM9PBG', 'DgvZDa', 'murcswrREa', 'ue5sig51BwjLCIbTDxn0igjLigv4ywn0BhKGmtaGzgLNAxrZlG', 'BwvZC2fNzq', 'r0vu', 'l2fWAs9MyxjLtg9VA3vWlW', 'sw5JB21WBgv0zsbKyxrHlIbqBgvHC2uGChjVDMLKzsbHBgWGCMvXDwLYzwqGzMLLBgrZlG', 'Dg9vChbLCKnHC2u', 'yxbWBgLJyxrPB24VANnVBG', 'mtG3mtK1mg13z0TUEq', 'C2HHmJu2'];

function decode(str) {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/=';
    let raw = '', out = '';
    for(let i=0, temp, char, j=0; char=str.charAt(j++); ~char&&(temp=i%4?temp*64+char:char,i++%4)?raw+=String.fromCharCode(255&temp>>(-2*i&6)):0){
        char = chars.indexOf(char);
    }
    for(let k=0; k<raw.length; k++){
        out += '%' + ('00' + raw.charCodeAt(k).toString(16)).slice(-2);
    }
    return decodeURIComponent(out);
}

list.forEach((s, idx) => {
    try {
        console.log(`Index ${idx + 499}: ${decode(s)}`);
    } catch(e) {}
});
