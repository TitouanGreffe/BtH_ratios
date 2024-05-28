import weighted
from matplotlib.cbook import violin_stats
import matplotlib.pyplot as plt
from scipy import stats
import statsmodels.api as sm
import math as m
import pandas as pd
import logging
import numpy as np



class byproduct_host_ratio:
    """
    This is a class to clean data of mineral resources estimates (see https://doi.org/10.5382/Geo-and-Mining-11 for more information about
    ore reserves and mineral resources categories) and calculate byproduct-to-host ratio i.e. the mass ratio of a byproduct (e.g. tellurium)
     and a host (e.g. copper) in an ore (e.g. porphyry)
    """

    def __init__(self,path,hbratiofile,sheetname,recoveryrate_general,recoveryrate_specific):
        print("Hello World")
        self.path = path
        self.hbratiofile = hbratiofile
        self.sheetname = sheetname
        self.recoveryrate_general = recoveryrate_general
        self.recoveryrate_specific = recoveryrate_specific

        # set up logging tool
        self.logger = logging.getLogger('Host_byproducts_ratio_results')
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = []
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        self.logger.propagate = False
        
    def recovery_function_concentration(self,element:str,concentration:float, source:str):
        """
        function for Gallium in bauxite should provide element == 'Ga' and source == 'Bauxite' or 'Karst' or 'Laterite'
        concentration should be provided in ppm
        Output is recovery rate in %
        :param element: Element from which you want to obtain the recovery rate
        :param concentration: Concentration of the element in part per million (ppm)
        :param source: Name of ore or brine from which the element is to be recovered
        :return: value of recovery rate in %
        """
        self.element = element
        self.c_e = concentration
        self.source = source
        if self.element == "Fe":
            "Iron recovery efficiency as function of iron concentration from figure S2.2 of https://doi.org/10.1038/s41467-021-22245-6"
            if self.c_e*1E4 < 0.20:
                self.rr = 0.5
            elif self.c_e*1E4 > 0.70:
                self.rr = 0.95
            else:
                self.rr = 0.2787*np.log(self.c_e*1E4)+ 1.0407

        if self.element == "Ga":
            if self.source == "Laterite" or self.source == "Karst" or self.source == "Bauxite":
                """ Gallium recovery function as function of Gallium concentration in bauxite from fig 3 of https://doi.org/10.1016/j.resourpol.2015.11.005"""
                if self.c_e < 35.17:
                    self.rr = 0
                elif self.c_e > 150:
                    self.rr = 65/100
                else:
                    self.rr = (5E-5*self.c_e**3-0.019*self.c_e**2+2.6278*self.c_e-71.087)/100
        return(self.rr)

    def calc_pot_acc_hb_ratios(self):
        '''
        This function calculates the potentially accessible byproduct-to-host ratio for all deposits in the dataset that have
        an host element specified in "Host" column
        :return: It writes the results in a new sheet called "results_pot_acc_ResC" in the input excel file
        '''
        self.df = pd.read_excel(self.path+self.hbratiofile,sheet_name = self.sheetname)
        'index_col for data_rr_general is the index of the column "Deposit type" as the deposit type as per ResC sheet '
        self.data_rr_general = pd.read_excel(self.path + self.hbratiofile, sheet_name=self.recoveryrate_general,index_col=0)
        'index_col for data_rr_specific is the index of the column "Project_name" as the name of the deposit as per ResC sheet '
        self.data_rr_specific = pd.read_excel(self.path + self.hbratiofile, sheet_name=self.recoveryrate_specific,index_col=5)
        self.host = self.df["Host"].copy('deep')
        self.host_byproducts = pd.DataFrame(index=self.df.index,columns=["Project_name","Deposit_type","Tonnage","Region"]).fillna("")
        for i, index in enumerate(self.df.index[1:]):
            row_host = self.host[i]
            if not row_host:
                self.logger.info("There is no host indicated on column Host and row %s",i)
            if row_host not in self.df.columns:
                self.logger.info("The host indicated "+str(row_host)+" is not an element of self.df.columns from line %s",i)
            else:
                'assign recovery rate to host according to deposit type, multiplied by smelter/refinery RR '
                self.rr_host = self.data_rr_general.loc[self.data_rr_general["Element"] == self.host[i]].loc["Undefined"].loc["Max_RR_ALL"]
                for column in self.df.columns[13:76]:  ## indicate the number of the columns containing element content
                    j = self.df.columns.get_loc(column)
                    if not self.df.iloc[i,j]:
                        pass
                    if type(self.df.iloc[i,j]) is str:
                        'print(self.df.iloc[i,j])'
                    if self.df.iloc[i,j] >0 and j != self.df.columns.get_loc(row_host):
                        self.rr_b = self.data_rr_general.loc[self.data_rr_general["Element"] == column].loc["Undefined"].loc["Max_RR_ALL"]
                        self.hb_acc = (self.df.iloc[i,j]*self.rr_b)/(self.df.loc[i,row_host]*self.rr_host)
                        self.name_col = str(column)+" / "+str(row_host)
                        self.host_byproducts.loc[i, "Project_name"] = self.df.loc[i, "Project_name"]
                        self.host_byproducts.loc[i,"Deposit_type"] = self.df.loc[i,"Deposit_type"]
                        self.host_byproducts.loc[i,"Ore tonnage"]= self.df.loc[i,row_host]/1000000
                        self.host_byproducts.loc[i,"Region"] = self.df.loc[i,"Region"]
                        if self.name_col not in self.host_byproducts.columns:
                            'to create an new column with the new pair from which Htb ratios can be now be filled'
                            self.host_byproducts = self.host_byproducts.reindex(columns=self.host_byproducts.columns.tolist() + [self.name_col])
                        self.host_byproducts.loc[i,self.name_col] = self.hb_acc

        self.host_byproducts.replace('', np.nan, inplace=True)
        self.host_byproducts.dropna(how="all",inplace=True)

        with pd.ExcelWriter(self.path+self.hbratiofile, mode="a", engine="openpyxl") as writer:
            self.host_byproducts.to_excel(writer, sheet_name="results_pot_acc_"+self.sheetname)


    def calc_accessible_hb_ratios(self):
        '''
        This function calculates the accessible byproduct-to-host ratio for all deposits in the dataset that have
        an host element specified in "Host" column
        :return: It writes the results in a new sheet called "results_accessible_ResC" in the input excel file
        '''
        self.df = pd.read_excel(self.path+self.hbratiofile,sheet_name = self.sheetname)
        'index_col for data_rr_general is the index of the column "Deposit type" as the deposit type as per ResC sheet '
        self.data_rr_general = pd.read_excel(self.path + self.hbratiofile, sheet_name=self.recoveryrate_general,index_col=0)
        'index_col for data_rr_specific is the index of the column "Project_name" as the name of the deposit as per ResC sheet '
        self.data_rr_specific = pd.read_excel(self.path + self.hbratiofile, sheet_name=self.recoveryrate_specific,index_col=5)
        self.host = self.df["Host"].copy('deep')
        self.host_byproducts = pd.DataFrame(index=self.df.index,columns=["Project_name","Deposit_type","Tonnage","Region"]).fillna("")
        self.recovery_rate_data = pd.DataFrame(index=self.df.index,
                                            columns=["Project_name", "Deposit_type", "Tonnage", "Region"]).fillna("")
        for i, index in enumerate(self.df.index[1:]):
            row_host = self.host[i]
            if not row_host:
                self.logger.info("There is no host indicated on column Host and row %s",i)
            if row_host not in self.df.columns:
                self.logger.info("The host indicated "+str(row_host)+" is not an element of self.df.columns from line %s",i)
            else:
                j_host = self.df.columns.get_loc(row_host)
                'assign recovery rate to host according to deposit type, multiplied by smelter/refinery RR '
                try:
                    self.rr_host = self.recovery_function_concentration(row_host,self.df.iloc[i,j_host]/self.df.loc[index,"Tonnage"],self.df.loc[index,"Deposit_type"])* \
                                   self.data_rr_general.loc[self.data_rr_general["Element"] == self.host[i]].loc["Undefined"].loc["Smelter_Refinery_RR"]
                    self.rr_host_data = "Concentration_specific_Host"
                except:
                    pass
                try:
                    print("Deposit type specific RR for host " + self.host[i]+" in "+self.df.loc[i, "Project_name"])
                    self.rr_host = self.data_rr_general.loc[self.data_rr_general["Element"] == self.host[i]].loc[
                        self.df["Deposit_type"][i]].loc["RR_ALL"]
                    self.rr_host_data = "Deposit_type_specific_Host"
                except:
                    pass
                try:
                    'self.a is just a test if no error'
                    self.a = self.data_rr_specific.loc[self.df.loc[i, "Project_name"]].loc[self.df.loc[i, "Host"]]
                    if not m.isnan(self.a):
                        self.rr_host = \
                            (self.a / 100) * self.data_rr_general.loc[self.data_rr_general["Element"] == self.host[i]].loc["Undefined"].loc["Smelter_Refinery_RR"]
                        print("Element-and-deposit specific RR for host " + self.host[i]+" in "+self.df.loc[i, "Project_name"])
                        self.rr_host_data = "Element_Deposit_Specific_Host"
                except:
                    print("Undefined RR for host "+self.host[i])
                    self.rr_host = self.data_rr_general.loc[self.data_rr_general["Element"] == self.host[i]].loc["Undefined"].loc["RR_ALL"]
                    self.rr_host_data = "Generic_Host"
                for column in self.df.columns[13:76]:  ## indicate the number of the columns containing element content
                    j = self.df.columns.get_loc(column)
                    if not self.df.iloc[i,j]:
                        pass
                    if type(self.df.iloc[i,j]) is str:
                        'print(self.df.iloc[i,j])'
                    if self.df.iloc[i,j] >0 and j != self.df.columns.get_loc(row_host):
                        'assign recovery rate to each byproduct according to deposit type, multiplied by smelter/refinery RR '
                        try:
                            self.rr_b = self.recovery_function_concentration(column,self.df.iloc[i,j]/self.df.loc[index,"Tonnage"],self.df.loc[index,"Deposit_type"])
                            print("RR as function of concentration of "+str(column)+" from "+str(self.df.loc[index,"Deposit_type"]))
                            self.rr_byproduct_data = "Concentration_specific_Byproduct"
                        except:
                            pass
                        try:
                            self.rr_b = self.data_rr_general.loc[self.data_rr_general["Element"] == column].loc[self.df["Deposit_type"][i]].loc["RR_ALL"]
                            self.rr_byproduct_data = "Deposit_type_specific_Byproduct"
                        except:
                            pass
                        try:
                            'self.b and self.c is just to test if no error'
                            self.b = self.data_rr_specific.loc[self.df.loc[i, "Project_name"]].loc[column]
                            self.c = self.data_rr_general.loc[self.data_rr_general["Element"] == column].loc["Undefined"].loc["Smelter_Refinery_RR"]
                            if not m.isnan(self.b) and not m.isnan(self.c):
                                self.rr_b = (self.b / 100)*self.c
                                print("Specific RR for " + str(column) + " in deposit " + str(self.df.loc[i, "Project_name"]))
                                self.rr_byproduct_data = "Element_Deposit_Specific_Byproduct"
                        except:
                            self.rr_b = self.data_rr_general.loc[self.data_rr_general["Element"] == column].loc["Undefined"].loc["RR_ALL"]
                            self.rr_byproduct_data = "Generic_Byproduct"
                        self.hb_acc = (self.df.iloc[i,j]*self.rr_b)/(self.df.loc[i,row_host]*self.rr_host)
                        self.name_col = str(column)+" / "+str(row_host)
                        self.host_byproducts.loc[i, "Project_name"] = self.df.loc[i, "Project_name"]
                        self.host_byproducts.loc[i,"Deposit_type"] = self.df.loc[i,"Deposit_type"]
                        self.host_byproducts.loc[i,"Tonnage"]= self.df.loc[i,row_host]/1000000
                        self.host_byproducts.loc[i,"Region"] = self.df.loc[i,"Region"]
                        self.recovery_rate_data.loc[i, "Project_name"] = self.df.loc[i, "Project_name"]
                        self.recovery_rate_data.loc[i, "Deposit_type"] = self.df.loc[i, "Deposit_type"]
                        self.recovery_rate_data.loc[i, "Ore tonnage"] = self.df.loc[i, row_host] / 1000000
                        self.recovery_rate_data.loc[i, "Region"] = self.df.loc[i, "Region"]
                        self.rr_data_status = self.rr_host_data + ";" + self.rr_byproduct_data
                        if self.name_col not in self.host_byproducts.columns:
                            'to create an new column with the new pair from which Htb ratios can be now be filled'
                            self.host_byproducts = self.host_byproducts.reindex(columns=self.host_byproducts.columns.tolist() + [self.name_col])
                        self.host_byproducts.loc[i,self.name_col] = self.hb_acc
                        self.recovery_rate_data.loc[i,self.name_col] = self.rr_data_status

        self.host_byproducts.replace('', np.nan, inplace=True)
        self.host_byproducts.dropna(how="all",inplace=True)

        with pd.ExcelWriter(self.path+self.hbratiofile, mode="a", engine="openpyxl") as writer:
            self.host_byproducts.to_excel(writer, sheet_name="results_accessible_"+self.sheetname)
            self.recovery_rate_data.to_excel(writer, sheet_name="rr_data_" + self.sheetname)


    def calc_available_hb_ratios(self):
        '''
        This function calculates the available byproduct-to-host ratio for all deposits in the dataset that have
        an host element specified in "Host" column
        :return: It writes the results in a new sheet called "results_av_ResC" in the input excel file
        '''
        self.df = pd.read_excel(self.path+self.hbratiofile,sheet_name = self.sheetname)
        self.host = self.df["Host"].copy('deep')
        self.host_byproducts = pd.DataFrame(index=self.df.index,columns=["Project_name","Deposit_type","Tonnage","Region"]).fillna("")
        for i, index in enumerate(self.df.index[1:]):
            row_host = self.host[i]
            if not row_host:
                self.logger.info("There is no host indicated on row Host and line %s",i)
            if row_host not in self.df.columns:
                self.logger.info("The host indicated "+str(row_host)+" is not an element of self.df.columns from line %s",i)
            else:
                for column in self.df.columns[13:76]:  ## indicate the number of the columns containing element content
                    j = self.df.columns.get_loc(column)
                    if not self.df.iloc[i,j]:
                        pass
                    if type(self.df.iloc[i,j]) is str:
                        print(self.df.iloc[i,j])
                    if self.df.iloc[i,j] >0 and j != self.df.columns.get_loc(row_host):
                        self.hb = self.df.iloc[i,j]/self.df.loc[i,row_host]
                        self.name_col = str(column)+" / "+str(row_host)
                        self.host_byproducts.loc[i,"Project_name"] = self.df.loc[i,"Project_name"]
                        self.host_byproducts.loc[i,"Deposit_type"] = self.df.loc[i,"Deposit_type"]
                        self.host_byproducts.loc[i,"Ore tonnage"]= self.df.loc[i,row_host]/1000000
                        self.host_byproducts.loc[i,"Region"] = self.df.loc[i,"Region"]
                        if self.name_col not in self.host_byproducts.columns:
                            'to create an new column with the new pair from which Htb ratios can be now be filled'
                            self.host_byproducts = self.host_byproducts.reindex(columns=self.host_byproducts.columns.tolist() + [self.name_col])
                        self.host_byproducts.loc[i,self.name_col] = self.hb
                #Add column with 1 to be able to plot the unweighted distribution of BtH ratios as per plot in figure 2 of the manuscript
                if 'All equal' not in self.host_byproducts.columns:
                    self.host_byproducts = self.host_byproducts.reindex(columns=self.host_byproducts.columns.tolist() + ['All equal'])
                self.host_byproducts.loc[i, 'All equal'] = 1

        self.host_byproducts.replace('', np.nan, inplace=True)
        self.host_byproducts.dropna(how="all",inplace=True)

        with pd.ExcelWriter(self.path+self.hbratiofile, mode="a", engine="openpyxl") as writer:
            self.host_byproducts.to_excel(writer, sheet_name="results_av_"+self.sheetname)


    def vdensity_with_weights(self,weights):
        ''' Outer function allows innder function access to weights. Matplotlib
        needs function to take in data and coords, so this seems like only way
        to 'pass' custom density function a set of weights
        function from jquacinella/violin_weighted_plot.py
        '''

        def vdensity(data,coords):
            ''' Custom matplotlib weighted violin stats function '''
            # Using weights from closure, get KDE from statsmodels
            weighted_cost = sm.nonparametric.KDEUnivariate(data)
            weighted_cost.fit(fft=False, weights=weights)

            # Return y-values for graph of KDE by evaluating on coords
            return weighted_cost.evaluate(coords)

        return vdensity

    def custom_violin_stats(self,col):
        # Get weighted median and mean (using weighted module for median)
        self.col = col
        data = self.host_byproducts.iloc[1:, 1:].iloc[:, self.col].to_numpy()
        weights = self.host_byproducts.iloc[1:, 0].to_numpy()
        median = weighted.quantile_1D(data, weights, 0.5)
        mean, sumw = np.ma.average(data, weights=list(weights), returned=True)

        # Use matplotlib violin_stats, which expects a function that takes in data and coords
        # which we get from closure above
        results = violin_stats(data, self.vdensity_with_weights(weights), points=len(weights))

        # Update result dictionary with our updated info
        results[0][u"mean"] = mean
        results[0][u"median"] = median

        # No need to do this, since it should be populated from violin_stats
        # results[0][u"min"] =  np.min(data)
        # results[0][u"max"] =  np.max(data)

        return results




