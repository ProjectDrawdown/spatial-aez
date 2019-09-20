function [Class, BroadClass] = KoppenGeiger(T,P,classes)
%   [Class, BroadClass] = KoppenGeiger(T,P,classes)
%
%   Classify monthly temperature and preciptiation climatologies according
%   to the Koppen-Geiger climate classification. The T and P inputs
%   represent the temperature and preciptiation climatologies,
%   respectively. T and P should be provided as three dimensional arrays
%   with the third dimension representing time (12 months). The temperature
%   data should have units degrees Celsius and the precipitation data units
%   mm/month.
%
%   The classes input relates the class symbols (e.g., Dwa) to specific and
%   broad numeric identifiers (e.g., 21 and 4, respectively). classes 
%   should be a cell array with the first column containing the numeric
%   identifier of the specific class, the second column containing the 
%   numeric identifier of the broad class, and the third column containing
%   the symbol. Other columns are not used in this function. This is an 
%   example of the classes input:
%
%   classes = {...
%       1,1,'Af','Tropical, rainforest',[0 0 255];...
%       2,1,'Am','Tropical, monsoon',[0 120 255];...
%       3,1,'Aw','Tropical, savannah',[70 170 250];...
%       4,2,'BWh','Arid, desert, hot',[255 0 0];...
%       5,2,'BWk','Arid, desert, cold',[255 150 150];...
%       6,2,'BSh','Arid, steppe, hot',[245 165 0];...
%       7,2,'BSk','Arid, steppe, cold',[255 220 100];...
%       8,3,'Csa','Temperate, dry summer, hot summer',[255 255 0];...
%       9,3,'Csb','Temperate, dry summer, warm summer',[200 200 0];...
%       10,3,'Csc','Temperate, dry summer, cold summer',[150 150 0];...
%       11,3,'Cwa','Temperate, dry winter, hot summer',[150 255 150];...
%       12,3,'Cwb','Temperate, dry winter, warm summer',[100 200 100];...
%       13,3,'Cwc','Temperate, dry winter, cold summer',[50 150 50];...
%       14,3,'Cfa','Temperate, no dry season, hot summer',[200 255 80];...
%       15,3,'Cfb','Temperate, no dry season, warm summer',[100 255 80];...
%       16,3,'Cfc','Temperate, no dry season, cold summer',[50 200 0];...
%       17,4,'Dsa','Cold, dry summer, hot summer',[255 0 255];...
%       18,4,'Dsb','Cold, dry summer, warm summer',[200 0 200];...
%       19,4,'Dsc','Cold, dry summer, cold summer',[150 50 150];...
%       20,4,'Dsd','Cold, dry summer, very cold winter',[150 100 150];...
%       21,4,'Dwa','Cold, dry winter, hot summer',[170 175 255];...
%       22,4,'Dwb','Cold, dry winter, warm summer',[90 120 220];...
%       23,4,'Dwc','Cold, dry winter, cold summer',[75 80 180];...
%       24,4,'Dwd','Cold, dry winter, very cold winter',[50 0 135];...
%       25,4,'Dfa','Cold, no dry season, hot summer',[0 255 255];...
%       26,4,'Dfb','Cold, no dry season, warm summer',[55 200 255];...
%       27,4,'Dfc','Cold, no dry season, cold summer',[0 125 125];...
%       28,4,'Dfd','Cold, no dry season, very cold winter',[0 70 95];...
%       29,5,'ET','Polar, tundra',[178 178 178];...
%       30,5,'EF','Polar, frost',[102 102 102];...
%       };
%
%   Copyright 2018 Hylke Beck
%   www.gloh2o.org

T_ONDJFM = mean(T(:,:,[10 11 12 1 2 3]),3);
T_AMJJAS = mean(T(:,:,[4 5 6 7 8 9]),3);
tmp = T_AMJJAS>T_ONDJFM;
SUM_SEL = false(size(T));
SUM_SEL(:,:,[4 5 6 7 8 9]) = repmat(tmp,1,1,6);
SUM_SEL(:,:,[10 11 12 1 2 3]) = repmat(~tmp,1,1,6);
clear tmp

Pw = sum(P.*single(~SUM_SEL),3);
Ps = sum(P.*single(SUM_SEL),3);

Pdry = min(P,[],3);

%tmp = P; tmp(~SUM_SEL) = NaN; % Too slow
tmp = single(SUM_SEL); tmp(tmp==0) = NaN;
Psdry = nanmin(P.*tmp,[],3);
Pswet = nanmax(P.*tmp,[],3);
%tmp = P; tmp(SUM_SEL) = NaN; % Too slow
tmp = single(~SUM_SEL); tmp(tmp==0) = NaN;
Pwdry = nanmin(P.*tmp,[],3);
Pwwet = nanmax(P.*tmp,[],3);

MAT = mean(T,3);
MAP = sum(P,3);
Tmon10 = sum(T>10,3);
Thot = max(T,[],3);
Tcold = min(T,[],3);

Pthresh = 2*MAT+14;
Pthresh(Pw*2.333>Ps) = 2*MAT(Pw*2.333>Ps);
Pthresh(Ps*2.333>Pw) = 2*MAT(Ps*2.333>Pw)+28;

B = MAP < 10*Pthresh;
BW = B & MAP < 5*Pthresh;
BWh = BW & MAT >= 18;
BWk = BW & MAT < 18;
BS = B & MAP >= 5*Pthresh;
BSh = BS & MAT >= 18;
BSk = BS & MAT < 18;

A = Tcold >= 18 & ~B; % Added "& ~B"
Af = A & Pdry >= 60;
Am = A & ~Af & Pdry >= 100-MAP/25;
Aw = A & ~Af & Pdry < 100-MAP/25;

C = Thot > 10 & Tcold > 0 & Tcold < 18 & ~B;
Cs = C & Psdry<40 & Psdry<Pwwet/3;
Cw = C & Pwdry<Pswet/10;
overlap = Cs & Cw;
Cs(overlap & Ps>Pw) = 0;
Cw(overlap & Ps<=Pw) = 0;
Csa = Cs & Thot >= 22;
Csb = Cs & ~Csa & Tmon10 >= 4;
Csc = Cs & ~Csa & ~Csb & Tmon10>=1 & Tmon10<4;
Cwa = Cw & Thot >= 22;
Cwb = Cw & ~Cwa & Tmon10 >= 4;
Cwc = Cw & ~Cwa & ~Cwb & Tmon10>=1 & Tmon10<4;
Cf = C & ~Cs & ~Cw;
Cfa = Cf & Thot >= 22;
Cfb = Cf & ~Cfa & Tmon10 >= 4;
Cfc = Cf & ~Cfa & ~Cfb & Tmon10>=1 & Tmon10<4;

D = Thot>10 & Tcold<=0 & ~B; % Added "& ~B"
Ds = D & Psdry<40 & Psdry<Pwwet/3;
Dw = D & Pwdry<Pswet/10;
overlap = Ds & Dw;
Ds(overlap & Ps>Pw) = 0;
Dw(overlap & Ps<=Pw) = 0;
Dsa = Ds & Thot>=22;
Dsb = Ds & ~Dsa & Tmon10 >= 4;
Dsd = Ds & ~Dsa & ~Dsb & Tcold<-38;
Dsc = Ds & ~Dsa & ~Dsb & ~Dsd;

Dwa = Dw & Thot>=22;
Dwb = Dw & ~Dwa & Tmon10 >= 4;
Dwd = Dw & ~Dwa & ~Dwb & Tcold<-38;
Dwc = Dw & ~Dwa & ~Dwb & ~Dwd;
Df = D & ~Ds & ~Dw;
Dfa = Df & Thot>=22;
Dfb = Df & ~Dfa & Tmon10 >= 4;
Dfd = Df & ~Dfa & ~Dfb & Tcold<-38;
Dfc = Df & ~Dfa & ~Dfb & ~Dfd;

E = Thot <= 10 & ~B; % Added "& ~B", and replaced "Thot<10" with "Thot<=10"
ET = E & Thot>0;
EF = E & Thot<=0;

Class = zeros(size(T(:,:,1)),'single');
BroadClass = zeros(size(T(:,:,1)),'single');
for cc = 1:length(classes(:,1))
    Class(eval(classes{cc,3})) = classes{cc,1};
    BroadClass(eval(classes{cc,3})) = classes{cc,2};
end

tmp = single(~isnan(P(:,:,1)+T(:,:,1)));
tmp(tmp==0) = NaN;
Class = Class.*tmp; % Faster than using a mask
BroadClass = BroadClass.*tmp;